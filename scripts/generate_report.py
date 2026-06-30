import os
import json
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENT_NAME = "swe_verified_100"
BASE_DIR = os.path.join(PROJECT_ROOT, "eval_results", EXPERIMENT_NAME)
SUMMARIES_DIR = os.path.join(BASE_DIR, "summaries")
REPORT_MD_PATH = os.path.join(BASE_DIR, "report_fp_fn.md")
REPORT_JSON_PATH = os.path.join(BASE_DIR, "summary_report.json")

def main():
    if not os.path.exists(SUMMARIES_DIR):
        print(f"Summaries directory not found: {SUMMARIES_DIR}")
        return

    summary_files = glob.glob(os.path.join(SUMMARIES_DIR, "*.json"))
    print(f"Found {len(summary_files)} summary files.")

    total_instances = len(summary_files)
    if total_instances == 0:
        print("No summaries to process.")
        return

    grader_passed_count = 0
    actual_passed_count = 0

    false_positives = []
    false_negatives = []
    true_failures = []

    for file_path in summary_files:
        instance_id = os.path.basename(file_path).replace(".json", "")
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error parsing JSON in {file_path}")
                continue
        
        is_fp = data.get("is_false_positive", False)
        is_fn = data.get("is_false_negative", False)
        failure_reason = data.get("failure_reason", "No reason provided.")

        # Determine original grader status based on definitions
        # If it's a false positive, it means grader passed it but it actually failed.
        # If it's a false negative, it means grader failed it but it actually passed.
        # Otherwise, if grader_match is true, we need to know if it passed or failed.
        
        # To accurately know if grader passed, we should read the original run status.
        # Since we didn't save the run status directly in the json (we could have), 
        # let's fetch it from the report.json directly here, or we can infer if the summary says 'passed'.
        # Let's fetch it from the logs directory to be 100% sure.
        
        model_mangled = "openrouter__xiaomi__mimo-v2.5-pro" # For this specific run
        report_json_path = os.path.join(PROJECT_ROOT, "logs", "run_evaluation", EXPERIMENT_NAME, model_mangled, instance_id, "report.json")
        grader_passed = False
        if os.path.exists(report_json_path):
            with open(report_json_path, "r", encoding="utf-8") as rf:
                report_data = json.load(rf)
                grader_passed = report_data.get(instance_id, {}).get("resolved", False)
        else:
            print(f"Warning: report.json not found for {instance_id}")

        if grader_passed:
            grader_passed_count += 1
            if is_fp:
                false_positives.append({"id": instance_id, "reason": failure_reason, "summary": data.get("summary")})
            else:
                actual_passed_count += 1
        else:
            if is_fn:
                actual_passed_count += 1
                false_negatives.append({"id": instance_id, "reason": failure_reason, "summary": data.get("summary")})
            else:
                true_failures.append({"id": instance_id, "reason": failure_reason, "summary": data.get("summary")})

    # Generate Markdown Report
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as md:
        md.write(f"# SWE Verified 100 Evaluation Report\n\n")
        
        md.write(f"## Metrics\n")
        md.write(f"- **Total Instances Processed:** {total_instances}\n")
        md.write(f"- **Pass Rate (Grader):** {grader_passed_count} / {total_instances} ({(grader_passed_count/total_instances)*100:.2f}%)\n")
        md.write(f"- **Pass Rate (Adjusted for FP/FN):** {actual_passed_count} / {total_instances} ({(actual_passed_count/total_instances)*100:.2f}%)\n\n")

        md.write(f"## 🚨 False Positives ({len(false_positives)})\n")
        md.write(f"Instances that the grader marked as PASSED, but the AI actually failed to solve the issue.\n\n")
        for fp in false_positives:
            md.write(f"### {fp['id']}\n")
            md.write(f"**Reason:** {fp['reason']}\n\n")

        md.write(f"## 🟢 False Negatives ({len(false_negatives)})\n")
        md.write(f"Instances that the grader marked as FAILED, but the AI actually correctly fixed the bug.\n\n")
        for fn in false_negatives:
            md.write(f"### {fn['id']}\n")
            md.write(f"**Reason:** {fn['reason']}\n\n")

        md.write(f"## ❌ True Failures ({len(true_failures)})\n")
        md.write(f"Instances that correctly failed.\n\n")
        for tf in true_failures:
            md.write(f"### {tf['id']}\n")
            md.write(f"**Reason:** {tf['reason']}\n\n")

    print(f"Report generated at {REPORT_MD_PATH}")

    # Generate Structured JSON Report
    json_report = {
        "metrics": {
            "total_instances_processed": total_instances,
            "grader_passed_count": grader_passed_count,
            "grader_pass_rate": grader_passed_count / total_instances if total_instances > 0 else 0,
            "actual_passed_count": actual_passed_count,
            "actual_pass_rate": actual_passed_count / total_instances if total_instances > 0 else 0,
        },
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_failures": true_failures
    }

    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as jf:
        json.dump(json_report, jf, indent=2)
        
    print(f"Structured JSON report generated at {REPORT_JSON_PATH}")

if __name__ == "__main__":
    main()
