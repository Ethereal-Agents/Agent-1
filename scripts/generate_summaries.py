import os
import json
import subprocess
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENT_NAME = "swe_verified_100"
BASE_DIR = os.path.join(PROJECT_ROOT, "eval_results", EXPERIMENT_NAME)
RESULTS_JSON_PATH = os.path.join(BASE_DIR, "results.json")
SUMMARIES_DIR = os.path.join(BASE_DIR, "summaries")
MAX_WORKERS = 5
MAX_RETRIES = 3

PROMPT_TEMPLATE = """You are an expert AI debugger and evaluation analyst. Your task is to analyze a completed autonomous agent run and provide a comprehensive post-mortem summary.

Here are the absolute paths to the data you need to read:
1. Trajectory (Agent's thoughts and actions): {traj_path}
2. Test Output (The final evaluation results): {test_out_path}
3. Final Patch (What the agent actually changed): {patch_path}
4. Run Status: {run_status}

Read these files carefully using your tools.
Then, output a JSON object with EXACTLY the following structure (do NOT output any other text, just the raw JSON):

```json
{{
  "summary": "### 🎯 Task & Outcome\\n... (include The Agent's Approach, Root Cause Analysis, and Takeaways & Optimization formatted as markdown. Keep it concise but insightful.)",
  "is_false_positive": false,
  "is_false_negative": false,
  "failure_reason": "Explain why it failed, or why it's a false positive/negative. If it's a true positive (passed correctly), you can just say 'Correctly resolved'.",
  "grader_match": true
}}
```

Definitions:
- `is_false_positive` (boolean): Set to `true` if the Run Status says PASSED, but the agent actually did not solve the issue correctly (e.g. introduced a regression, or the test was flawed and passed anyway).
- `is_false_negative` (boolean): Set to `true` if the Run Status says FAILED, but the patch actually correctly fixed the bug (e.g. test failed due to an environment issue or flaky test).
- `grader_match` (boolean): Set to `true` if the Run Status matches the actual reality of the patch (i.e. NOT a false positive and NOT a false negative).

IMPORTANT: Make sure your JSON is valid and properly escaped. Do not include any trailing commas.
"""

def extract_json(text):
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    
    # Try to find anything that looks like JSON if backticks are missing
    match = re.search(r"({.*})", text, re.DOTALL)
    if match:
         return match.group(1)
    return text

def process_instance(instance):
    instance_id = instance.get("instance_id")
    model_path = instance.get("model_name_or_path", "")
    model_mangled = model_path.replace("/", "__")

    logs_dir = os.path.join(
        PROJECT_ROOT, "logs", "run_evaluation", EXPERIMENT_NAME, model_mangled, instance_id
    )
    test_out_path = os.path.join(logs_dir, "test_output.txt")
    patch_path = os.path.join(logs_dir, "patch.diff")
    traj_path = instance.get("trajectory_path", "")
    report_json_path = os.path.join(logs_dir, "report.json")

    passed = False
    if os.path.exists(report_json_path):
        with open(report_json_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
            passed = report_data.get(instance_id, {}).get("resolved", False)
    
    run_status = "PASSED" if passed else "FAILED"
    out_file = os.path.join(SUMMARIES_DIR, f"{instance_id}.json")

    if os.path.exists(out_file):
        return True # Already processed

    prompt = PROMPT_TEMPLATE.format(
        traj_path=traj_path if os.path.exists(traj_path) else "NOT AVAILABLE",
        test_out_path=test_out_path if os.path.exists(test_out_path) else "NOT AVAILABLE",
        patch_path=patch_path if os.path.exists(patch_path) else "NOT AVAILABLE",
        run_status=run_status
    )

    for attempt in range(MAX_RETRIES):
        try:
            cmd = ["agy", "--print", prompt, "--dangerously-skip-permissions", "--print-timeout", "15m"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
            output = result.stdout
            
            json_str = extract_json(output)
            parsed = json.loads(json_str)
            
            # Validate required keys
            for key in ["summary", "is_false_positive", "is_false_negative", "failure_reason", "grader_match"]:
                if key not in parsed:
                    raise ValueError(f"Missing key in JSON: {key}")
            
            # Atomic write
            tmp_out_file = out_file + ".tmp"
            with open(tmp_out_file, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)
            os.rename(tmp_out_file, out_file)
            
            return True
        except subprocess.CalledProcessError as e:
            # Subprocess failed
            pass
        except (json.JSONDecodeError, ValueError) as e:
            # JSON parsing failed
            pass
        except Exception as e:
            pass
        
        # Backoff before retrying
        time.sleep((attempt + 1) * 5)
    
    return False

def main():
    os.makedirs(SUMMARIES_DIR, exist_ok=True)
    
    if not os.path.exists(RESULTS_JSON_PATH):
        print(f"Results file not found: {RESULTS_JSON_PATH}")
        return

    with open(RESULTS_JSON_PATH, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    print(f"Loaded {len(results)} instances. Starting generation with {MAX_WORKERS} workers...")
    
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_instance, instance): instance["instance_id"] for instance in results}
        
        with tqdm(total=len(futures), desc="Generating Summaries") as pbar:
            for future in as_completed(futures):
                instance_id = futures[future]
                try:
                    success = future.result()
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        print(f"\\nFailed to process {instance_id} after {MAX_RETRIES} retries.")
                except Exception as e:
                    fail_count += 1
                    print(f"\\nException processing {instance_id}: {e}")
                finally:
                    pbar.update(1)
    
    print(f"\\nFinished. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
