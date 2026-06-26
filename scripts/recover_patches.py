"""Script to recover patches from completed agent trajectories without using LLM calls.

This script replays the exact state-mutating tool calls (bash, edit, insert) from 
the trajectory.jsonl files into a fresh Docker environment, and then extracts the 
final patch via git diff.

Usage:
  python scripts/recover_patches.py --run-id <YOUR_RUN_ID> --dataset princeton-nlp/SWE-bench_Verified
"""

import argparse
import json
import os
import sys

# Ensure project root is in PYTHONPATH
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from eval.dataset import load_swe_bench  # noqa: E402
from eval.grader import write_predictions  # noqa: E402
from eval.models import TaskResult  # noqa: E402
from eval.runner import _build_swebench_image, _extract_patch, _get_docker_client  # noqa: E402
from tools.environment import DockerEnvironment  # noqa: E402
from tools.registry import execute_tool, initialize_tools  # noqa: E402


def check_trajectory_finished(trajectory_path: str):
    """Determine if a trajectory finished successfully and extract mutating calls."""
    is_done = False
    mutating_calls = []
    step_count = 0

    if not os.path.exists(trajectory_path):
        return False, [], 0

    with open(trajectory_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
                
                # Check for assistant messages
                if msg.get("role") == "assistant":
                    step_count += 1
                    if "tool_calls" in msg and msg["tool_calls"]:
                        consecutive_no_tools = 0
                        for tc in msg["tool_calls"]:
                            func = tc.get("function", {})
                            name = func.get("name")
                            args_str = func.get("arguments", "{}")
                            
                            try:
                                args_dict = json.loads(args_str)
                            except json.JSONDecodeError:
                                args_dict = {}

                            if name == "finish":
                                is_done = True
                            elif name in ["bash", "edit", "insert"]:
                                mutating_calls.append((name, args_dict))
                    else:
                        consecutive_no_tools += 1
                        if consecutive_no_tools >= 3:
                            is_done = True
            except json.JSONDecodeError:
                pass

    # If the step count hit our configured max limit, it's also considered done.
    from config import MAX_STEPS
    if step_count >= MAX_STEPS:
        is_done = True

    return is_done, mutating_calls, step_count


def recover_patch_for_instance(instance: dict, mutating_calls: list, namespace: str) -> str:
    """Replays mutating calls in Docker and extracts the patch."""
    instance_id = instance["instance_id"]
    container = None
    try:
        print(f"[{instance_id}] Rebuilding image...")
        image_name = _build_swebench_image(instance, namespace=namespace)
        
        client = _get_docker_client()
        print(f"[{instance_id}] Starting container...")
        container = client.containers.run(
            image_name,
            command="sleep infinity",
            detach=True,
            remove=True,
        )
        
        conda_prefix = (
            "if [ -f /opt/miniconda3/etc/profile.d/conda.sh ]; then "
            "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed || true; "
            "elif [ -f /miniconda/etc/profile.d/conda.sh ]; then "
            "source /miniconda/etc/profile.d/conda.sh && conda activate testbed || true; "
            "fi;"
        )
        env = DockerEnvironment(
            container_id=container.id, 
            command_prefix=conda_prefix,
        )
        initialize_tools(env)
        
        print(f"[{instance_id}] Executing {len(mutating_calls)} mutating tool calls...")
        for name, args in mutating_calls:
            # We don't care about the tool output here, just the state mutation
            execute_tool(name, args)
            
        print(f"[{instance_id}] Extracting patch...")
        patch = _extract_patch(container.id, instance["base_commit"])
        return patch or ""
        
    finally:
        if container:
            try:
                container.stop(timeout=5)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Recover patches from trajectories.")
    parser.add_argument("--run-id", required=True, help="The run_id of the interrupted eval run.")
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Verified", help="HuggingFace dataset name.")
    parser.add_argument("--split", default="test", help="Dataset split.")
    parser.add_argument("--namespace", default="", help="Docker namespace for swebench.")
    args = parser.parse_args()

    run_dir = os.path.join(base_dir, "eval_results", args.run_id)
    trajectories_dir = os.path.join(run_dir, "trajectories")
    
    if not os.path.exists(trajectories_dir):
        print(f"ERROR: Trajectories directory not found: {trajectories_dir}")
        sys.exit(1)

    print("Loading dataset...")
    instances = load_swe_bench(args.dataset, args.split)
    instance_map = {inst["instance_id"]: inst for inst in instances}

    recovered_results = []
    
    for instance_id in os.listdir(trajectories_dir):
        # The trajectory logger creates a nested directory because of how RECALL_RUNS_DIR was set
        traj_path = os.path.join(trajectories_dir, instance_id, instance_id, "trajectory.jsonl")
        
        if not os.path.exists(traj_path):
            continue
            
        if instance_id not in instance_map:
            print(f"[{instance_id}] Skipped (not found in dataset '{args.dataset}')")
            continue
            
        is_done, mutating_calls, step_count = check_trajectory_finished(traj_path)
        
        if is_done:
            print(f"\n--- Recovering {instance_id} ---")
            patch = recover_patch_for_instance(instance_map[instance_id], mutating_calls, args.namespace)
            
            result = TaskResult(
                instance_id=instance_id,
                model_name_or_path="recovered",
                model_patch=patch,
                exit_reason="recovered",
                total_steps=step_count,
                total_tokens=0,
                total_cost=0.0,
                duration_seconds=0.0,
                trajectory_path=traj_path,
            )
            recovered_results.append(result)
            
            from dataclasses import asdict
            result_path = os.path.join(trajectories_dir, instance_id, "result.json")
            with open(result_path, "w") as f:
                json.dump(asdict(result), f, indent=2)
                
            print(f"[{instance_id}] Patch extracted. Length: {len(patch)} chars.")
        else:
            print(f"[{instance_id}] Skipped (trajectory not finished)")

    if recovered_results:
        out_file = os.path.join(run_dir, "recovered_predictions.jsonl")
        write_predictions(recovered_results, out_file)
        print(f"\nSuccessfully recovered {len(recovered_results)} patches.")
        print(f"Predictions written to: {out_file}")
        print("You can now grade them using:")
        print(f"python -m eval.run_eval --grade-only --predictions {out_file} --run-id {args.run_id}")
    else:
        print("\nNo finished trajectories found to recover.")


if __name__ == "__main__":
    main()
