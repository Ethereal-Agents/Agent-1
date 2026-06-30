"""Task loading and prompt formatting for ML Research Bench."""

import json
import os


def load_mlrb_tasks(tasks_dir: str, task_ids: list[str] = None) -> list[dict]:
    """Load task configurations from the ML Research Bench directories.
    
    Args:
        tasks_dir: The directory containing ml_research_bench tasks.
        task_ids: Optional list of task IDs to filter by.
        
    Returns:
        List of task.json dicts.
    """
    manifest_path = os.path.join(tasks_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")
        
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
        
    tasks = []
    for entry in manifest.get("tasks", []):
        tid = entry["id"]
        if task_ids and tid not in task_ids:
            continue
            
        task_json_path = os.path.join(tasks_dir, tid, "task.json")
        if not os.path.exists(task_json_path):
            print(f"WARNING: task.json missing for {tid}, skipping.")
            continue
            
        with open(task_json_path, "r") as f:
            task_config = json.load(f)
            
        # Inject the task directory path into the config for convenience
        task_config["_task_dir"] = os.path.join(tasks_dir, tid)
        tasks.append(task_config)
        
    return tasks


def format_mlrb_prompt(task_config: dict) -> str:
    """Format the task configuration into the agent's issue_description.
    
    The prompt is constructed to clearly describe the task, the working directory,
    and how the agent should verify its work.
    """
    prompt = [
        f"# Task: {task_config.get('title', task_config['task_id'])}",
        "",
        "## Description",
        task_config.get("description", "Solve the task described in the repo."),
        "",
        "## Working Directory",
        "Your code is mounted at: `/workspace`",
        "",
        "## Verification",
        "Your implementation will be evaluated against a comprehensive grading test suite.",
        "However, a basic set of dev tests is provided in the repository to help you verify your approach.",
    ]
    
    dev_test_cmd = task_config.get("dev_test_command")
    if dev_test_cmd:
        prompt.extend([
            "",
            "To verify basic correctness, run:",
            f"```bash\n{dev_test_cmd}\n```"
        ])
        
    return "\n".join(prompt)
