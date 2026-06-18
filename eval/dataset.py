"""Dataset loading, filtering, and prompt formatting for SWE-bench."""

import json
import os


def load_swe_bench(dataset_name: str, split: str = "test") -> list[dict]:
    """Load SWE-bench dataset from HuggingFace. Returns list of instance dicts."""
    from datasets import load_dataset

    print(f"Loading dataset: {dataset_name} ({split})")
    ds = load_dataset(dataset_name, split=split)
    instances = [dict(row) for row in ds]
    print(f"Loaded {len(instances)} instances.")
    return instances


def filter_by_instance_ids(instances: list[dict], ids: list[str]) -> list[dict]:
    """Filter dataset to only the given instance IDs."""
    id_set = set(ids)
    filtered = [inst for inst in instances if inst["instance_id"] in id_set]
    missing = id_set - {inst["instance_id"] for inst in filtered}
    if missing:
        print(f"WARNING: {len(missing)} instance ID(s) not found in dataset: {missing}")
    return filtered


def filter_by_tier(instances: list[dict], tier_file: str) -> list[dict]:
    """Filter dataset using a tier JSON config file (e.g., configs/tier_10.json)."""
    if not os.path.exists(tier_file):
        raise FileNotFoundError(f"Tier file not found: {tier_file}")
    with open(tier_file, "r") as f:
        tier_config = json.load(f)
    ids = tier_config.get("instance_ids", [])
    print(f"Tier file '{tier_file}' defines {len(ids)} instances.")
    return filter_by_instance_ids(instances, ids)


def format_task_prompt(instance: dict) -> str:
    """Format a SWE-bench instance into the agent's issue_description string.

    This is passed directly to Agent.run(issue_description=...).
    The existing system prompt already instructs the agent to resolve GitHub issues.
    """
    parts = [
        f"Repository: {instance['repo']}",
        "",
        "## Issue",
        instance["problem_statement"],
    ]
    if instance.get("hints_text", "").strip():
        parts += ["", "## Hints", instance["hints_text"].strip()]
    return "\n".join(parts)
