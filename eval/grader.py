"""Grader: writes predictions JSONL and invokes the official swebench harness."""

import json
import os

from eval.models import GradeReport, TaskResult


def write_predictions(results: list[TaskResult], output_path: str) -> str:
    """Write predictions in the swebench submission format.

    Each line: {"instance_id": "...", "model_name_or_path": "...", "model_patch": "..."}
    Returns the path to the written file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        for result in results:
            f.write(
                json.dumps(
                    {
                        "instance_id": result.instance_id,
                        "model_name_or_path": result.model_name_or_path,
                        "model_patch": result.model_patch or "",
                    }
                )
                + "\n"
            )
    print(f"Predictions written: {output_path} ({len(results)} instances)")
    return output_path


def grade(
    predictions_path: str,
    dataset_name: str,
    run_id: str,
    output_dir: str,
    max_workers: int = 4,
    namespace: str = "",
    timeout: int = 1800,
) -> GradeReport:
    """Invoke the official swebench harness (main()) to grade predictions.

    swebench main() will:
    1. Load predictions from the JSONL file
    2. Build/pull Docker images per instance
    3. Apply each model_patch and run FAIL_TO_PASS + PASS_TO_PASS tests
    4. Write per-instance report.json logs and a top-level run report
    """
    from swebench.harness.run_evaluation import main as swebench_main

    print(f"\nGrading with swebench harness (run_id={run_id})...")
    swebench_main(
        dataset_name=dataset_name,
        split="test",
        instance_ids=None,
        predictions_path=predictions_path,
        max_workers=max_workers,
        force_rebuild=False,
        cache_level="env",
        clean=False,
        open_file_limit=4096,
        run_id=run_id,
        timeout=timeout,
        namespace=namespace or None,  # None = use swebench default
        rewrite_reports=False,
        modal=False,
        report_dir=output_dir,
    )

    return parse_results(run_id, output_dir)


def parse_results(run_id: str, output_dir: str) -> GradeReport:
    """Parse the swebench run report to build a GradeReport.

    swebench writes a top-level report JSON that contains resolved_ids,
    unresolved_ids, error_ids, etc. We look for it in output_dir.
    """
    # swebench writes: <model_name>.<run_id>.json in the CWD / report_dir
    per_instance: dict[str, str] = {}
    report_data: dict = {}

    # Search for the run report file
    search_dirs = [output_dir, "."]
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue
        for fname in os.listdir(search_dir):
            if fname.endswith(f".{run_id}.json"):
                fpath = os.path.join(search_dir, fname)
                with open(fpath) as f:
                    report_data = json.load(f)

                # If swebench dumped it in the root folder, move it to output_dir to keep workspace clean
                if search_dir == ".":
                    import shutil

                    try:
                        target_path = os.path.join(output_dir, fname)
                        shutil.move(fpath, target_path)
                    except Exception:
                        pass  # safe fallback if move fails
                break
        if report_data:
            break

    if not report_data:
        # Fallback: try reading per-instance report.json files from the log dir
        return _parse_per_instance_logs(run_id, output_dir)

    for iid in report_data.get("resolved_ids", []):
        per_instance[iid] = "resolved"
    for iid in report_data.get("unresolved_ids", []):
        per_instance[iid] = "unresolved"
    for iid in report_data.get("error_ids", []):
        per_instance[iid] = "error"
    # empty_patch_ids are effectively unresolved
    for iid in report_data.get("empty_patch_ids", []):
        per_instance.setdefault(iid, "unresolved")

    total = len(per_instance)
    resolved = sum(1 for v in per_instance.values() if v == "resolved")
    unresolved = sum(1 for v in per_instance.values() if v == "unresolved")
    errored = sum(1 for v in per_instance.values() if v == "error")

    return GradeReport(
        run_id=run_id,
        total=total,
        resolved=resolved,
        unresolved=unresolved,
        errored=errored,
        resolution_rate=resolved / total if total else 0.0,
        per_instance=per_instance,
    )


def _parse_per_instance_logs(run_id: str, output_dir: str) -> GradeReport:
    """Fallback: parse individual report.json files from the swebench log dir.

    Log path: logs/run_evaluation/<run_id>/<model>/<instance_id>/report.json
    Each file: {instance_id: {"resolved": bool, ...}}
    """
    per_instance: dict[str, str] = {}
    log_base = os.path.join("logs", "run_evaluation", run_id)

    if not os.path.exists(log_base):
        print(f"WARNING: No swebench results found at {log_base} or {output_dir}")
        return GradeReport(
            run_id=run_id,
            total=0,
            resolved=0,
            unresolved=0,
            errored=0,
            resolution_rate=0.0,
            per_instance={},
        )

    # Walk: logs/run_evaluation/<run_id>/<model>/<instance_id>/report.json
    for model_dir in os.listdir(log_base):
        model_path = os.path.join(log_base, model_dir)
        if not os.path.isdir(model_path):
            continue
        for instance_id in os.listdir(model_path):
            report_path = os.path.join(model_path, instance_id, "report.json")
            if not os.path.exists(report_path):
                per_instance[instance_id] = "error"
                continue
            try:
                with open(report_path) as f:
                    data = json.load(f)
                if data.get(instance_id, {}).get("resolved"):
                    per_instance[instance_id] = "resolved"
                else:
                    per_instance[instance_id] = "unresolved"
            except Exception:
                per_instance[instance_id] = "error"

    total = len(per_instance)
    resolved = sum(1 for v in per_instance.values() if v == "resolved")
    unresolved = sum(1 for v in per_instance.values() if v == "unresolved")
    errored = sum(1 for v in per_instance.values() if v == "error")

    return GradeReport(
        run_id=run_id,
        total=total,
        resolved=resolved,
        unresolved=unresolved,
        errored=errored,
        resolution_rate=resolved / total if total else 0.0,
        per_instance=per_instance,
    )
