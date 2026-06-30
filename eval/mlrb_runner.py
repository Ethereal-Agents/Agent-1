"""Task runner for ML Research Bench."""

import json
import os
import time
import traceback
from dataclasses import asdict

from agent.loop import Agent
from eval.mlrb_dataset import format_mlrb_prompt
from eval.mlrb_grader import parse_pytest_output
from eval.models import MLRBConfig, MLRBTaskResult
from tools.environment import DockerEnvironment
from tools.registry import initialize_tools


def _infer_exit_reason(agent: Agent) -> str:
    from config import MAX_STEPS
    if agent.step_count >= MAX_STEPS:
        return "max_steps"
    return "submitted"


def run_single_mlrb_task(task_config: dict, config: MLRBConfig, output_dir: str) -> MLRBTaskResult:
    """Run a single MLRB task.
    
    1. Setup container and run agent
    2. Extract patch
    3. Inject grading tests and grade in the same container
    4. Cleanup and return
    """
    task_id = task_config["task_id"]
    model = config.model
    start_time = time.time()
    task_dir = task_config["_task_dir"]
    
    # Setup directories
    trajectories_dir = os.path.join(output_dir, "trajectories")
    instance_run_dir = os.path.join(trajectories_dir, task_id)
    os.makedirs(instance_run_dir, exist_ok=True)
    trajectory_path = os.path.join(instance_run_dir, "trajectory.jsonl")
    result_path = os.path.join(instance_run_dir, "result.json")
    
    if config.resume and os.path.exists(result_path):
        try:
            with open(result_path, "r") as f:
                data = json.load(f)
            print(f"[{task_id}] Resuming from saved result.json")
            return MLRBTaskResult(**data)
        except Exception as e:
            print(f"[{task_id}] Failed to load result.json: {e}")
            
    if os.path.exists(trajectory_path):
        open(trajectory_path, "w").close()

    env = None
    try:
        # We need a copy of the repo in the container that isn't volume-mounted directly 
        # so the agent doesn't modify the host files. DockerEnvironment `mount_dir` actually 
        # uses volumes for speed, but for this benchmark we want isolated copies.
        # However, the current DockerEnvironment uses: `volumes={mount_path: {"bind": "/workspace", "mode": "rw"}}`
        # To prevent host mutation, we should copy the repo to a temp dir first, then mount that.
        import shutil
        import tempfile
        
        repo_src = os.path.join(task_dir, "repo")
        tmp_repo_dir = tempfile.mkdtemp(prefix=f"mlrb_{task_id}_")
        # Copy contents of repo_src to tmp_repo_dir
        for item in os.listdir(repo_src):
            s = os.path.join(repo_src, item)
            d = os.path.join(tmp_repo_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks=True)
            else:
                shutil.copy2(s, d)
                
        # We need to initialize git so we can extract a patch later
        subprocess_cmd = f"cd {tmp_repo_dir} && git init && git add . && git commit -m 'Initial state'"
        import subprocess
        subprocess.run(subprocess_cmd, shell=True, check=True, capture_output=True)

        print(f"[{task_id}] Starting container...")
        env = DockerEnvironment(
            image=task_config.get("docker_image", config.docker_image),
            mount_dir=tmp_repo_dir,
            setup_command=task_config.get("setup_commands"),
        )
        initialize_tools(env)
        
        print(f"[{task_id}] Running agent...")
        os.environ["RECALL_RUNS_DIR"] = trajectories_dir
        agent = Agent(model=model, instance_id=task_id)
        
        # Determine if arxiv is enabled
        if not config.enable_arxiv:
            # We would disable the arxiv tool here, assuming it's managed via registry or config
            pass # TODO: Tool disabling logic
            
        agent.run(issue_description=format_mlrb_prompt(task_config))
        exit_reason = _infer_exit_reason(agent)
        
        print(f"[{task_id}] Agent finished. Extracting patch...")
        patch_result = env.run_bash("cd /workspace && git diff HEAD", timeout=30)
        patch = patch_result.stdout if patch_result.returncode == 0 else ""
        
        print(f"[{task_id}] Injecting grading tests...")
        grading_dir = os.path.join(task_dir, "grading")
        for test_file in os.listdir(grading_dir):
            if test_file.endswith(".py"):
                host_path = os.path.join(grading_dir, test_file)
                container_path = f"/workspace/{test_file}"
                with open(host_path, "r") as f:
                    env.write_file(container_path, f.read())
                    
        print(f"[{task_id}] Grading...")
        grade_cmd = task_config.get("grade_test_command", "pytest -v --tb=short")
        grade_result = env.run_bash(f"cd /workspace && {grade_cmd}", timeout=120)
        passed, failed, total = parse_pytest_output(grade_result.stdout)
        
        print(f"[{task_id}] Done — exit={exit_reason}, score={passed}/{total}")
        
        task_result = MLRBTaskResult(
            task_id=task_id,
            category=task_config.get("category", "unknown"),
            difficulty=task_config.get("difficulty", "unknown"),
            model_name=model,
            model_patch=patch,
            exit_reason=exit_reason,
            tests_passed=passed,
            tests_failed=failed,
            tests_total=total,
            test_score=passed / total if total > 0 else 0.0,
            pass_at_1=(passed == total and total > 0),
            total_steps=agent.step_count,
            total_tokens=agent.cumulative_tokens,
            total_cost=agent.cumulative_cost,
            duration_seconds=time.time() - start_time,
            trajectory_path=trajectory_path,
            pytest_output=grade_result.stdout,
        )
        
        with open(result_path, "w") as f:
            json.dump(asdict(task_result), f, indent=2)
            
        return task_result

    except Exception as e:
        print(f"[{task_id}] ERROR: {e}")
        traceback.print_exc()
        return MLRBTaskResult(
            task_id=task_id,
            category=task_config.get("category", "unknown"),
            difficulty=task_config.get("difficulty", "unknown"),
            model_name=model,
            model_patch=None,
            exit_reason="error",
            tests_passed=0,
            tests_failed=0,
            tests_total=0,
            test_score=0.0,
            pass_at_1=False,
            total_steps=0,
            total_tokens=0,
            total_cost=0.0,
            duration_seconds=time.time() - start_time,
            trajectory_path=trajectory_path,
            pytest_output=str(e),
        )
    finally:
        if env:
            env.cleanup()
        # Clean up temp dir
        try:
            import shutil
            if 'tmp_repo_dir' in locals() and os.path.exists(tmp_repo_dir):
                shutil.rmtree(tmp_repo_dir)
        except Exception:
            pass
