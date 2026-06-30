import os
from eval.reporter import tag_failure, tag_failures, compute_metrics, generate_report
from eval.models import GradeReport, TaskResult

def test_tag_failure():
    r = TaskResult("a", "m", "p", "submitted", 1, 1, 1.0, 1.0, "t")
    assert tag_failure(r, "resolved") == "resolved"
    assert tag_failure(r, "unresolved") == "tests_failed"
    
    r2 = TaskResult("a", "m", "", "submitted", 1, 1, 1.0, 1.0, "t")
    assert tag_failure(r2, "unresolved") == "no_patch"
    
    r3 = TaskResult("a", "m", "p", "error", 1, 1, 1.0, 1.0, "t")
    assert tag_failure(r3, "unresolved") == "environment_failure"
    
    r4 = TaskResult("a", "m", "p", "timeout", 1, 1, 1.0, 1.0, "t")
    assert tag_failure(r4, "unresolved") == "timeout"
    
    r5 = TaskResult("a", "m", "p", "max_steps", 1, 1, 1.0, 1.0, "t")
    assert tag_failure(r5, "unresolved") == "max_steps"

def test_tag_failures():
    results = [
        TaskResult("a", "m", "p", "submitted", 1, 1, 1.0, 1.0, "t"),
        TaskResult("b", "m", "p", "error", 1, 1, 1.0, 1.0, "t"),
        TaskResult("c", "m", "p", "submitted", 1, 1, 1.0, 1.0, "t") # not in grade report -> unresolved
    ]
    report = GradeReport("r", 3, 1, 1, 1, 0.33, {"a": "resolved", "b": "error"})
    tags = tag_failures(results, report)
    assert len(tags) == 3
    assert tags[0] == {"instance_id": "a", "grade": "resolved", "tag": "resolved"}
    assert tags[1] == {"instance_id": "b", "grade": "error", "tag": "environment_failure"}
    assert tags[2] == {"instance_id": "c", "grade": "unresolved", "tag": "tests_failed"}

def test_compute_metrics():
    results = [TaskResult("a", "m", "p", "submitted", 1, 1, 1.0, 1.0, "t")]
    report = GradeReport("r", 1, 1, 0, 0, 1.0, {"a": "resolved"})
    metrics = compute_metrics(results, report, "123")
    assert metrics.run_id == "123"
    assert metrics.pass_at_1 == 1.0
    assert metrics.exit_reason_counts == {"submitted": 1}

def test_generate_report(tmp_path):
    results = [TaskResult("a", "m", "p", "submitted", 1, 1, 1.0, 1.0, "t")]
    report = GradeReport("r", 1, 1, 0, 0, 1.0, {"a": "resolved"})
    metrics = compute_metrics(results, report, "123")
    
    out = tmp_path / "out"
    generate_report(metrics, results, report, str(out))
    
    assert (out / "summary.json").exists()
    assert (out / "instances.csv").exists()
    assert (out / "failures.json").exists()
    assert (out / "report.md").exists()
