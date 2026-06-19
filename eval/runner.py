"""Task runner: sets up Docker environments, runs the agent, extracts patches."""

import concurrent.futures
import os
import subprocess
import time
import traceback

from eval.dataset import format_task_prompt
from eval.models import EvalConfig, TaskResult


def _build_swebench_image(instance: dict, namespace: str) -> str:
    """Build/pull the official SWE-bench Docker image for a given instance.

    Returns the image tag string (e.g., 'swebench/sweb.eval.x86_64.sympy__sympy-20590:latest').
    Uses the swebench.harness.docker_build module.
    """
    from swebench.harness.docker_build import build_instance_image
    from swebench.harness.run_evaluation import make_test_spec

    # make_test_spec creates the specification for the instance
    test_spec = make_test_spec(instance, namespace=namespace or "swebench")

    # build_instance_image builds the per-instance image (repo + commit + test fixtures)
    build_instance_image(
        test_spec=test_spec,
        client=_get_docker_client(),
        logger=None,
        nocache=False,
    )
    return test_spec.instance_image_key


def _get_docker_client():
    """Return a docker client, raising a clear error if Docker is not running."""
    import docker

    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        raise EnvironmentError(
            "Docker is not running or not reachable. "
            "Please start Docker/OrbStack before running the eval harness."
        )


def _extract_patch(container_id: str, base_commit: str) -> str | None:
    """Extract the agent's changes from inside the container as a unified git diff.

    Uses `git diff <base_commit>` to capture all changes — unstaged, staged, *and*
    committed — relative to the exact starting state from the SWE-bench task.
    """
    result = subprocess.run(
        ["docker", "exec", container_id, "git", "diff", base_commit],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout
    return None


def run_single_task(instance: dict, config: EvalConfig, output_dir: str) -> TaskResult:
    """Run the full eval pipeline on a single SWE-bench task instance.

    Steps:
    1. Build/pull the official swebench Docker image for the task
    2. Start a container and attach a DockerEnvironment to it
    3. Run the agent's ReAct loop with the formatted issue prompt
    4. Extract the patch via `git diff <base_commit>`
    5. Cleanup the container
    6. Return a TaskResult
    """
    from agent.loop import Agent
    from tools.environment import DockerEnvironment
    from tools.registry import initialize_tools

    instance_id = instance["instance_id"]
    model = config.model
    start_time = time.time()
    container = None

    # Trajectory goes into output_dir/<instance_id>/
    instance_run_dir = os.path.join(output_dir, "trajectories", instance_id)
    os.makedirs(instance_run_dir, exist_ok=True)
    trajectory_path = os.path.join(instance_run_dir, "trajectory.jsonl")

    try:
        # --- Step 1: Build image ---
        print(f"[{instance_id}] Building swebench image...")
        image_name = _build_swebench_image(instance, namespace=config.namespace)

        # --- Step 2: Start container and attach DockerEnvironment ---
        client = _get_docker_client()
        container = client.containers.run(
            image_name,
            command="sleep infinity",
            detach=True,
            remove=True,
        )
        print(f"[{instance_id}] Container started: {container.short_id}")

        env = DockerEnvironment(container_id=container.id)
        initialize_tools(env)

        # --- Step 3: Run the agent ---
        # Override RUNS_DIR so trajectory is saved in our output dir
        os.environ["RECALL_RUNS_DIR"] = instance_run_dir

        agent = Agent(model=model, instance_id=instance_id)
        agent.run(issue_description=format_task_prompt(instance))

        exit_reason = _infer_exit_reason(agent)

        # --- Step 4: Extract the patch ---
        patch = _extract_patch(container.id, instance["base_commit"])
        print(
            f"[{instance_id}] Done — exit={exit_reason}, "
            f"steps={agent.step_count}, patch={'YES' if patch else 'EMPTY'}"
        )

        return TaskResult(
            instance_id=instance_id,
            model_name_or_path=model,
            model_patch=patch or "",  # empty string = no changes (swebench expects a string)
            exit_reason=exit_reason,
            total_steps=agent.step_count,
            total_tokens=agent.cumulative_tokens,
            total_cost=agent.cumulative_cost,
            duration_seconds=time.time() - start_time,
            trajectory_path=trajectory_path,
        )

    except Exception as e:
        print(f"[{instance_id}] ERROR: {e}")
        traceback.print_exc()
        return TaskResult(
            instance_id=instance_id,
            model_name_or_path=model,
            model_patch="",
            exit_reason="error",
            total_steps=0,
            total_tokens=0,
            total_cost=0.0,
            duration_seconds=time.time() - start_time,
            trajectory_path=trajectory_path,
        )
    finally:
        if container:
            try:
                container.stop(timeout=5)
            except Exception:
                pass


def _infer_exit_reason(agent) -> str:
    """Determine why the agent loop exited based on agent state."""
    from config import MAX_STEPS, MAX_SUBMISSIONS

    if agent.submit_count >= MAX_SUBMISSIONS:
        return "max_submissions"
    if agent.step_count >= MAX_STEPS:
        return "max_steps"
    return "submitted"


def _budget_check(cumulative_cost: float, config: EvalConfig) -> None:
    """Emit a warning if cumulative cost crosses a budget threshold."""
    threshold = config.budget_warn_threshold
    if threshold <= 0:
        return
    pct = (cumulative_cost / threshold) * 100
    for level in sorted(config.budget_warn_interval_pct, reverse=True):
        if pct >= level:
            print(
                f"\n⚠️  BUDGET WARNING: ${cumulative_cost:.3f} spent "
                f"({pct:.1f}% of ${threshold:.2f} threshold)\n"
            )
            break


def run_batch(
    instances: list[dict],
    config: EvalConfig,
    output_dir: str,
) -> list[TaskResult]:
    """Run the agent on a batch of instances, optionally in parallel.

    Uses ProcessPoolExecutor so each agent gets its own Python process and
    Docker container. max_workers=1 is sequential (safe default).
    """
    from swebench.harness.docker_build import build_env_images

    results: list[TaskResult] = []
    cumulative_cost = 0.0
    total = len(instances)

    print("Checking and building base environment images if necessary...")
    build_env_images(
        client=_get_docker_client(),
        dataset=instances,
        force_rebuild=False,
        max_workers=config.max_workers_inference,
        namespace=config.namespace or "swebench",
        instance_image_tag="latest",
        env_image_tag="latest",
    )

    if config.max_workers_inference <= 1:
        # Sequential — simple and easy to debug
        for i, instance in enumerate(instances, 1):
            print(f"\n{'='*60}")
            print(f"Instance {i}/{total}: {instance['instance_id']}")
            print(f"{'='*60}")
            result = run_single_task(instance, config, output_dir)
            results.append(result)
            cumulative_cost += result.total_cost
            _budget_check(cumulative_cost, config)
    else:
        # Parallel — each instance runs in its own subprocess
        print(f"Running {total} instances with {config.max_workers_inference} workers (parallel)")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=config.max_workers_inference
        ) as executor:
            futures = {
                executor.submit(run_single_task, inst, config, output_dir): inst["instance_id"]
                for inst in instances
            }
            for future in concurrent.futures.as_completed(futures):
                instance_id = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    cumulative_cost += result.total_cost
                    _budget_check(cumulative_cost, config)
                    print(f"[{instance_id}] Completed ({len(results)}/{total})")
                except Exception as e:
                    print(f"[{instance_id}] Future raised: {e}")

    return results
