"""CLI entry point for running ML Research Bench tasks."""

import argparse
import os
import uuid
from datetime import datetime

from eval.mlrb_dataset import load_mlrb_tasks
from eval.mlrb_runner import run_single_mlrb_task
from eval.models import MLRBConfig


def parse_args():
    parser = argparse.ArgumentParser(description="Run ML Research Bench tasks.")
    parser.add_argument("--tasks", type=str, help="Comma-separated list of task IDs to run")
    parser.add_argument("--run-id", type=str, help="Unique identifier for this run")
    parser.add_argument("--model", type=str, help="Model to use")
    parser.add_argument("--enable-arxiv", action="store_true", help="Enable arxiv search tool (for ablation)")
    parser.add_argument("--resume", action="store_true", help="Resume from previous run")
    return parser.parse_args()


def main():
    args = parse_args()
    
    config = MLRBConfig()
    if args.model:
        config.model = args.model
    if args.enable_arxiv:
        config.enable_arxiv = True
    if args.resume:
        config.resume = True
        
    run_id = args.run_id or f"mlrb-{datetime.now().strftime('%Y%m%d_%H%M%S')}-{uuid.uuid4().hex[:6]}"
    output_dir = os.path.join(config.output_dir, run_id)
    os.makedirs(output_dir, exist_ok=True)
    
    task_ids = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
    
    try:
        tasks = load_mlrb_tasks(config.tasks_dir, task_ids)
    except FileNotFoundError as e:
        print(f"Error loading tasks: {e}")
        print("Please ensure you run this from the project root and the tasks exist.")
        return

    if not tasks:
        print("No tasks found to run.")
        return
        
    print(f"Starting run {run_id} with {len(tasks)} tasks.")
    print(f"Model: {config.model}, Arxiv enabled: {config.enable_arxiv}")
    
    results = []
    for i, task in enumerate(tasks, 1):
        print(f"\n{'='*60}")
        print(f"Task {i}/{len(tasks)}: {task['task_id']}")
        print(f"{'='*60}")
        
        result = run_single_mlrb_task(task, config, output_dir)
        results.append(result)
        
    # TODO: generate summary report
    print("\nRun complete.")
    for r in results:
        status = "PASSED" if r.pass_at_1 else "FAILED"
        print(f"  {r.task_id}: {status} ({r.tests_passed}/{r.tests_total} tests)")

if __name__ == "__main__":
    main()
