"""Eval harness for SWE-bench Verified."""

from eval.dataset import filter_by_instance_ids, filter_by_tier, format_task_prompt, load_swe_bench
from eval.grader import grade, parse_results, write_predictions
from eval.models import EvalConfig, EvalMetrics, GradeReport, TaskResult
from eval.reporter import compute_metrics, generate_report, tag_failures
from eval.runner import run_batch, run_single_task

__all__ = [
    # models
    "EvalConfig",
    "TaskResult",
    "GradeReport",
    "EvalMetrics",
    # dataset
    "load_swe_bench",
    "filter_by_instance_ids",
    "filter_by_tier",
    "format_task_prompt",
    # runner
    "run_single_task",
    "run_batch",
    # grader
    "write_predictions",
    "grade",
    "parse_results",
    # reporter
    "compute_metrics",
    "generate_report",
    "tag_failures",
]
