"""
SWE-bench Verified eval harness CLI.

Usage examples:
  # 10-instance dev tier
  python -m eval.run_eval --tier 10 --run-id dev-001

  # Specific instances
  python -m eval.run_eval --instance-ids "sympy__sympy-20590,django__django-11039"

  # Full SWE-bench Verified
  python -m eval.run_eval --dataset princeton-nlp/SWE-bench_Verified --run-id full-001

  # Inference only (skip grading)
  python -m eval.run_eval --tier 10 --inference-only --run-id dev-001

  # Grade only (reuse saved predictions)
  python -m eval.run_eval --grade-only --predictions eval_results/dev-001/predictions.jsonl --run-id dev-001

CLI Arguments:
  --dataset            HuggingFace dataset name (default: princeton-nlp/SWE-bench_Verified)
  --split              Dataset split (default: test)
  --tier               Predefined instance subset: 10, 50, or 300 (loads configs/tier_N.json)
  --instance-ids       Comma-separated instance IDs for targeted runs
  --model              LiteLLM model string (overrides config)
  --run-id             Unique identifier for this eval run (auto-generated if omitted)
  --output-dir         Output directory (default: eval_results/)
  --max-workers-inference  Parallel agent runs (default: from config)
  --max-workers-grading    Parallel swebench grading workers (default: from config)
  --timeout            Per-task timeout in seconds (default: 1800)
  --inference-only     Run only the agent inference phase (skip grading)
  --grade-only         Run only the grading phase (requires --predictions)
  --predictions        Path to existing predictions.jsonl (for --grade-only)
  --namespace          Docker namespace for swebench (default: "" for ARM/OrbStack)
  --budget-warn        Budget warning threshold in USD (default: 5.0)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime


def _load_eval_config(args):
    """Build EvalConfig from the eval_config.yaml, then apply CLI overrides."""
    import yaml

    from eval.models import EvalConfig

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "configs", "eval_config.yaml")

    cfg = EvalConfig()  # start with defaults

    if os.path.exists(config_path):
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        eval_sec = raw.get("eval", {})
        agent_sec = raw.get("agent", {})
        budget_sec = raw.get("budget", {})

        cfg.dataset = eval_sec.get("dataset", cfg.dataset)
        cfg.split = eval_sec.get("split", cfg.split)
        cfg.max_workers_grading = eval_sec.get("max_workers_grading", cfg.max_workers_grading)
        cfg.max_workers_inference = eval_sec.get("max_workers_inference", cfg.max_workers_inference)
        cfg.timeout_per_task = eval_sec.get("timeout_per_task", cfg.timeout_per_task)
        cfg.output_dir = eval_sec.get("output_dir", cfg.output_dir)
        cfg.namespace = eval_sec.get("namespace", cfg.namespace)
        cfg.model = agent_sec.get("model", cfg.model)
        cfg.budget_warn_threshold = budget_sec.get("warn_threshold_usd", cfg.budget_warn_threshold)

    # CLI overrides
    if args.dataset:
        cfg.dataset = args.dataset
    if args.split:
        cfg.split = args.split
    if args.model:
        cfg.model = args.model
    if args.max_workers_inference is not None:
        cfg.max_workers_inference = args.max_workers_inference
    if args.max_workers_grading is not None:
        cfg.max_workers_grading = args.max_workers_grading
    if args.timeout is not None:
        cfg.timeout_per_task = args.timeout
    if args.output_dir:
        cfg.output_dir = args.output_dir
    if args.namespace is not None:
        cfg.namespace = args.namespace
    if args.budget_warn is not None:
        cfg.budget_warn_threshold = args.budget_warn
    if args.resume:
        cfg.resume = args.resume

    return cfg


def _resolve_instances(args, instances: list[dict], base_dir: str) -> list[dict]:
    """Apply --tier or --instance-ids filters to the full dataset."""
    from eval.dataset import filter_by_instance_ids, filter_by_tier

    if args.instance_ids:
        ids = [i.strip() for i in args.instance_ids.split(",") if i.strip()]
        return filter_by_instance_ids(instances, ids)

    if args.tier:
        tier_file = os.path.join(base_dir, "configs", f"tier_{args.tier}.json")
        return filter_by_tier(instances, tier_file)

    return instances


def main():
    parser = argparse.ArgumentParser(
        prog="python -m eval.run_eval",
        description="SWE-bench Verified eval harness for recall-agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--split", type=str, default=None)
    parser.add_argument(
        "--tier",
        type=int,
        choices=[10, 50, 300],
        default=None,
        help="Load predefined instance subset from configs/tier_N.json",
    )
    parser.add_argument(
        "--instance-ids", type=str, default=None, help="Comma-separated instance IDs"
    )
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument(
        "--run-id", type=str, default=None, help="Unique run identifier (auto-generated if omitted)"
    )
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--max-workers-inference", type=int, default=None)
    parser.add_argument("--max-workers-grading", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--inference-only", action="store_true")
    parser.add_argument("--grade-only", action="store_true")
    parser.add_argument(
        "--predictions",
        type=str,
        default=None,
        help="Path to predictions.jsonl (required for --grade-only)",
    )
    parser.add_argument("--namespace", type=str, default=None)
    parser.add_argument("--budget-warn", type=float, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume interrupted run by skipping finished instances and clearing unfinished trajectories.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the current progress/status of the run and exit.",
    )

    args = parser.parse_args()

    # Validate
    if args.grade_only and not args.predictions:
        parser.error("--grade-only requires --predictions <path>")
    if args.inference_only and args.grade_only:
        parser.error("--inference-only and --grade-only are mutually exclusive")

    # Setup
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base_dir)  # ensure imports resolve from project root

    config = _load_eval_config(args)

    run_id = (
        args.run_id or f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    run_output_dir = os.path.join(base_dir, config.output_dir, run_id)
    os.makedirs(run_output_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print("recall-agent eval harness")
    print(f"Run ID:  {run_id}")
    print(f"Model:   {config.model}")
    print(f"Dataset: {config.dataset} ({config.split})")
    print(f"Output:  {run_output_dir}")
    print(f"{'=' * 60}\n")

    if args.status:
        from eval.dataset import load_swe_bench

        all_instances = load_swe_bench(config.dataset, config.split)
        instances = _resolve_instances(args, all_instances, base_dir)
        if not instances:
            print("ERROR: No instances to evaluate after filtering.")
            sys.exit(1)
        _print_run_status(run_output_dir, instances)
        sys.exit(0)

    predictions_path = os.path.join(run_output_dir, "predictions.jsonl")

    # ------------------------------------------------------------------ #
    # Phase 1: Inference                                                   #
    # ------------------------------------------------------------------ #
    if not args.grade_only:
        from eval.dataset import load_swe_bench
        from eval.grader import write_predictions
        from eval.runner import run_batch

        all_instances = load_swe_bench(config.dataset, config.split)
        instances = _resolve_instances(args, all_instances, base_dir)

        if not instances:
            print("ERROR: No instances to evaluate after filtering.")
            sys.exit(1)

        print(f"Evaluating {len(instances)} instances with model '{config.model}'...\n")
        results = run_batch(instances, config, run_output_dir)

        # Save results metadata
        write_predictions(results, predictions_path)
        _save_results_json(results, run_output_dir)
    else:
        # Grade-only: load results from existing predictions if saved alongside
        predictions_path = args.predictions
        results = _load_results_json(run_output_dir)
        print(f"Grade-only mode. Using predictions: {predictions_path}")

    # ------------------------------------------------------------------ #
    # Phase 2: Grading                                                     #
    # ------------------------------------------------------------------ #
    if not args.inference_only:
        from eval.grader import grade
        from eval.reporter import compute_metrics, generate_report

        grade_report = grade(
            predictions_path=predictions_path,
            dataset_name=config.dataset,
            run_id=run_id,
            output_dir=run_output_dir,
            max_workers=config.max_workers_grading,
            namespace=config.namespace,
        )

        if results:
            metrics = compute_metrics(results, grade_report, run_id)
            generate_report(metrics, results, grade_report, run_output_dir)
            _print_summary(metrics)
        else:
            print(f"\nGrading complete. Resolved: {grade_report.resolved}/{grade_report.total}")
    else:
        print("\nInference-only mode. Skipping grading.")
        print(
            f"To grade later: python -m eval.run_eval --grade-only "
            f"--predictions {predictions_path} --run-id {run_id}"
        )


def _save_results_json(results: list, output_dir: str) -> None:
    """Persist TaskResult list as JSON for later grade-only runs."""
    from dataclasses import asdict

    path = os.path.join(output_dir, "results.json")
    with open(path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)


def _load_results_json(output_dir: str) -> list:
    """Load persisted TaskResult list, returns empty list if not found."""
    from eval.models import TaskResult

    path = os.path.join(output_dir, "results.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        raw = json.load(f)
    return [TaskResult(**r) for r in raw]


def _print_summary(metrics) -> None:
    print(f"\n{'=' * 60}")
    print(f"RESULTS — {metrics.run_id}")
    print(f"{'=' * 60}")
    print(
        f"  pass@1:          {metrics.pass_at_1:.1%} ({metrics.resolved}/{metrics.total_instances})"
    )
    print(f"  cost (total):    ${metrics.cost.total:.4f}")
    print(f"  cost (per task): ${metrics.cost.mean:.4f} avg")
    print(f"  tokens (avg):    {metrics.tokens.mean:,.0f}")
    print(f"  steps (avg):     {metrics.turns.mean:.1f}")
    print(f"{'=' * 60}\n")


def _print_run_status(output_dir: str, instances: list) -> None:
    """Print a progress table showing LLM, Patch, and Grading status for all instances."""
    import json

    report_path = os.path.join(output_dir, "report.json")
    graded = set()
    if os.path.exists(report_path):
        try:
            with open(report_path) as f:
                r = json.load(f)
                graded.update(r.get("resolved", []))
                graded.update(r.get("unresolved", []))
                graded.update(r.get("error", []))
        except Exception:
            pass

    print(f"Status for run in: {output_dir}")
    print("-" * 65)
    print(f"{'Instance ID':<35} | {'LLM Done':<10} | {'Patch':<7} | {'Graded'}")
    print("-" * 65)

    total = len(instances)
    done_llm = 0
    done_patch = 0
    done_graded = 0

    for inst in instances:
        instance_id = inst["instance_id"]
        result_path = os.path.join(output_dir, "trajectories", instance_id, "result.json")

        llm_done = "❌"
        patch_extracted = "❌"
        is_graded = "✅" if instance_id in graded else "❌"

        if os.path.exists(result_path):
            llm_done = "✅"
            done_llm += 1
            try:
                with open(result_path) as f:
                    data = json.load(f)
                if data.get("model_patch"):
                    patch_extracted = "✅"
                    done_patch += 1
            except Exception:
                pass

        if is_graded == "✅":
            done_graded += 1

        print(f"{instance_id:<35} | {llm_done:<10} | {patch_extracted:<7} | {is_graded}")

    print("-" * 65)
    print(f"Total: {total} instances")
    print(f"LLM Done: {done_llm}/{total}")
    print(f"Patches : {done_patch}/{total}")
    print(f"Graded  : {done_graded}/{total}")
    print("-" * 65)


if __name__ == "__main__":
    main()
