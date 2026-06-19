"""
Create a SWE-bench Verified dataset subset with specific difficulty distributions.

Execution command example:
uv run python create_eval_dataset.py --easy 10 --medium 5 --hard 2 --output-dir eval_dataset
"""

import argparse
import json
import random
import os
from datasets import load_dataset

def count_changed_lines(patch):
    """Counts the number of added and removed lines in a git patch."""
    if not patch:
        return 0
        
    added = 0
    removed = 0
    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added += 1
        elif line.startswith('-') and not line.startswith('---'):
            removed += 1
    return added + removed

def main():
    parser = argparse.ArgumentParser(description="Create a SWE-bench Verified dataset subset.")
    parser.add_argument("--easy", type=int, default=0, help="Number of easy samples (< 20 lines changed).")
    parser.add_argument("--medium", type=int, default=0, help="Number of medium samples (20-100 lines changed).")
    parser.add_argument("--hard", type=int, default=0, help="Number of hard samples (> 100 lines changed).")
    parser.add_argument("--output-dir", "-o", type=str, default="eval_dataset", help="Output directory to save the JSON file.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    
    args = parser.parse_args()
    
    if args.easy == 0 and args.medium == 0 and args.hard == 0:
        print("Error: You must specify at least one difficulty level to sample from (e.g., --easy 10)")
        return
        
    print("Loading dataset princeton-nlp/SWE-bench_Verified...")
    # SWE-bench Verified only has a 'test' split
    dataset = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    
    easy_pool = []
    medium_pool = []
    hard_pool = []
    
    print("Sorting dataset by difficulty...")
    for row in dataset:
        patch = row["patch"]
        lines_changed = count_changed_lines(patch)
        
        if lines_changed < 20:
            easy_pool.append(row["instance_id"])
        elif 20 <= lines_changed <= 100:
            medium_pool.append(row["instance_id"])
        else:
            hard_pool.append(row["instance_id"])
            
    print(f"Pool sizes - Easy: {len(easy_pool)}, Medium: {len(medium_pool)}, Hard: {len(hard_pool)}")
    
    sampled_instances = []
    random.seed(args.seed)
    
    def sample_pool(pool, requested, name):
        if requested == 0:
            return []
        if requested > len(pool):
            print(f"Warning: Requested {requested} {name} samples, but only found {len(pool)}. Returning all available.")
            return pool.copy()
        return random.sample(pool, requested)
        
    easy_samples = sample_pool(easy_pool, args.easy, "easy")
    medium_samples = sample_pool(medium_pool, args.medium, "medium")
    hard_samples = sample_pool(hard_pool, args.hard, "hard")
    
    sampled_instances.extend(easy_samples)
    sampled_instances.extend(medium_samples)
    sampled_instances.extend(hard_samples)
    
    if not sampled_instances:
        print("No samples generated.")
        return
        
    # Ensure the instances are sorted to look clean
    sampled_instances.sort()
    
    # Construct descriptive filename and description
    parts = []
    dist_parts = []
    
    if len(easy_samples) > 0:
        parts.append(f"easy{len(easy_samples)}")
        dist_parts.append(f"easy: {len(easy_samples)}")
    if len(medium_samples) > 0:
        parts.append(f"medium{len(medium_samples)}")
        dist_parts.append(f"medium: {len(medium_samples)}")
    if len(hard_samples) > 0:
        parts.append(f"hard{len(hard_samples)}")
        dist_parts.append(f"hard: {len(hard_samples)}")
        
    filename_suffix = "_".join(parts)
    filename = f"swebench_verified_{filename_suffix}.json"
    
    distribution_str = ", ".join(dist_parts)
    description = f"{len(sampled_instances)}-instance dev tier using valid SWE-bench_Verified IDs (Distribution - {distribution_str})."
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    output_data = {
        "description": description,
        "dataset": "princeton-nlp/SWE-bench_Verified",
        "instance_ids": sampled_instances
    }
    
    output_file = os.path.join(args.output_dir, filename)
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)
        
    print(f"Successfully saved {len(sampled_instances)} instance IDs to {output_file}")

if __name__ == "__main__":
    main()
