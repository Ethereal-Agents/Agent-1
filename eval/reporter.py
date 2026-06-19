"""Reporter: metrics computation, failure tagging, and markdown report generation."""

import csv
import json
import os
from dataclasses import asdict
from datetime import datetime

from eval.models import EvalMetrics, GradeReport, StatSummary, TaskResult

# ---------------------------------------------------------------------------
# Heuristic failure taxonomy
# No LLM calls — pure signal from agent state and trajectory metadata.
# ---------------------------------------------------------------------------


def tag_failure(result: TaskResult, grade: str) -> str:
    """Return a single failure tag for a non-resolved instance.

    Heuristics (checked in priority order):
    - environment_failure: exit_reason == "error" (container/setup crash)
    - timeout: exit_reason == "timeout"
    - max_steps: exit_reason == "max_steps" (agent ran out of budget)
    - max_submissions: hit submission cap without passing tests
    - no_patch: agent exited cleanly but produced no code changes
    - tests_failed: agent submitted but tests didn't pass (default)
    """
    if grade == "resolved":
        return "resolved"
    if result.exit_reason == "error":
        return "environment_failure"
    if result.exit_reason == "timeout":
        return "timeout"
    if result.exit_reason == "max_steps":
        return "max_steps"
    if result.exit_reason == "max_submissions":
        return "max_submissions"
    if not result.model_patch or not result.model_patch.strip():
        return "no_patch"
    return "tests_failed"


def tag_failures(results: list[TaskResult], grade_report: GradeReport) -> list[dict]:
    """Return a list of {instance_id, grade, tag} dicts for all instances."""
    tags = []
    for result in results:
        grade = grade_report.per_instance.get(result.instance_id, "unresolved")
        tag = tag_failure(result, grade)
        tags.append({"instance_id": result.instance_id, "grade": grade, "tag": tag})
    return tags


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(
    results: list[TaskResult], grade_report: GradeReport, run_id: str
) -> EvalMetrics:
    """Aggregate per-instance results into summary statistics."""
    exit_counts: dict[str, int] = {}
    for r in results:
        exit_counts[r.exit_reason] = exit_counts.get(r.exit_reason, 0) + 1

    return EvalMetrics(
        run_id=run_id,
        pass_at_1=grade_report.resolution_rate,
        total_instances=grade_report.total,
        resolved=grade_report.resolved,
        unresolved=grade_report.unresolved,
        errored=grade_report.errored,
        cost=StatSummary.from_values([r.total_cost for r in results]),
        tokens=StatSummary.from_values([float(r.total_tokens) for r in results]),
        turns=StatSummary.from_values([float(r.total_steps) for r in results]),
        duration=StatSummary.from_values([r.duration_seconds for r in results]),
        exit_reason_counts=exit_counts,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(
    metrics: EvalMetrics,
    results: list[TaskResult],
    grade_report: GradeReport,
    output_dir: str,
) -> None:
    """Write summary.json, instances.csv, failures.json, and report.md."""
    os.makedirs(output_dir, exist_ok=True)

    failure_tags = tag_failures(results, grade_report)

    _write_summary_json(metrics, output_dir)
    _write_instances_csv(results, grade_report, failure_tags, output_dir)
    _write_failures_json(failure_tags, output_dir)
    _write_markdown_report(metrics, results, grade_report, failure_tags, output_dir)

    print(f"\nReport written to: {output_dir}/")


def _write_summary_json(metrics: EvalMetrics, output_dir: str) -> None:
    path = os.path.join(output_dir, "summary.json")
    with open(path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)


def _write_instances_csv(
    results: list[TaskResult],
    grade_report: GradeReport,
    failure_tags: list[dict],
    output_dir: str,
) -> None:
    tag_map = {t["instance_id"]: t["tag"] for t in failure_tags}
    path = os.path.join(output_dir, "instances.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "instance_id",
                "grade",
                "tag",
                "exit_reason",
                "steps",
                "tokens",
                "cost_usd",
                "duration_s",
            ]
        )
        for r in results:
            grade = grade_report.per_instance.get(r.instance_id, "N/A")
            writer.writerow(
                [
                    r.instance_id,
                    grade,
                    tag_map.get(r.instance_id, ""),
                    r.exit_reason,
                    r.total_steps,
                    r.total_tokens,
                    f"{r.total_cost:.4f}",
                    f"{r.duration_seconds:.1f}",
                ]
            )


def _write_failures_json(failure_tags: list[dict], output_dir: str) -> None:
    path = os.path.join(output_dir, "failures.json")
    with open(path, "w") as f:
        json.dump(failure_tags, f, indent=2)


def _write_markdown_report(
    metrics: EvalMetrics,
    results: list[TaskResult],
    grade_report: GradeReport,
    failure_tags: list[dict],
    output_dir: str,
) -> None:
    """Generate a clean, human-readable markdown report."""
    run_id = metrics.run_id
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Failure tag distribution
    tag_counts: dict[str, int] = {}
    for t in failure_tags:
        if t["grade"] != "resolved":
            tag_counts[t["tag"]] = tag_counts.get(t["tag"], 0) + 1

    lines = [
        f"# Eval Report — `{run_id}`",
        "",
        f"*Generated: {timestamp}*",
        "",
        "---",
        "",
        "## Results",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| **pass@1** | **{metrics.pass_at_1:.1%}** |",
        f"| Resolved | {metrics.resolved} / {metrics.total_instances} |",
        f"| Unresolved | {metrics.unresolved} |",
        f"| Errored | {metrics.errored} |",
        "",
        "## Cost & Usage",
        "",
        "| | Mean | Median | p95 | Total |",
        "|---|---|---|---|---|",
        f"| Cost (USD) | ${metrics.cost.mean:.4f} | ${metrics.cost.median:.4f} | ${metrics.cost.p95:.4f} | ${metrics.cost.total:.4f} |",
        f"| Tokens | {metrics.tokens.mean:,.0f} | {metrics.tokens.median:,.0f} | {metrics.tokens.p95:,.0f} | {metrics.tokens.total:,.0f} |",
        f"| Steps | {metrics.turns.mean:.1f} | {metrics.turns.median:.1f} | {metrics.turns.p95:.1f} | {metrics.turns.total:.0f} |",
        f"| Duration (s) | {metrics.duration.mean:.1f} | {metrics.duration.median:.1f} | {metrics.duration.p95:.1f} | {metrics.duration.total:.1f} |",
        "",
        "## Exit Reason Distribution",
        "",
        "| Exit Reason | Count |",
        "|---|---|",
    ]
    for reason, count in sorted(metrics.exit_reason_counts.items()):
        lines.append(f"| `{reason}` | {count} |")

    lines += [
        "",
        "## Failure Mode Analysis",
        "",
        "| Failure Tag | Count |",
        "|---|---|",
    ]
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{tag}` | {count} |")

    lines += [
        "",
        "## Per-Instance Results",
        "",
        "| Instance ID | Grade | Tag | Steps | Cost |",
        "|---|---|---|---|---|",
    ]
    tag_map = {t["instance_id"]: t for t in failure_tags}
    for r in sorted(results, key=lambda x: x.instance_id):
        grade = grade_report.per_instance.get(r.instance_id, "N/A")
        tag = tag_map.get(r.instance_id, {}).get("tag", "")
        grade_icon = "✅" if grade == "resolved" else "❌"
        lines.append(
            f"| `{r.instance_id}` | {grade_icon} {grade} | `{tag}` "
            f"| {r.total_steps} | ${r.total_cost:.4f} |"
        )

    path = os.path.join(output_dir, "report.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
