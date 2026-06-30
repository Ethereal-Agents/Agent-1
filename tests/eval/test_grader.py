import json
import os
from unittest import mock
from eval.grader import write_predictions, grade, parse_results, _parse_per_instance_logs
from eval.models import TaskResult

def test_write_predictions(tmp_path):
    out = tmp_path / "preds.jsonl"
    r = TaskResult(instance_id="a", model_name_or_path="m", model_patch="p", exit_reason="s", total_steps=1, total_tokens=1, total_cost=1.0, duration_seconds=1.0, trajectory_path="t")
    res = write_predictions([r], str(out))
    assert res == str(out)
    assert '{"instance_id": "a"' in out.read_text()

@mock.patch("swebench.harness.run_evaluation.main")
@mock.patch("eval.grader.parse_results")
def test_grade(mock_parse_results, mock_swebench_main, tmp_path):
    # Test grade and the delete files logic
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "test.123.json").write_text("dummy")
    (out_dir / "test.456.json").write_text("dummy") # different run_id
    
    mock_parse_results.return_value = "report"
    res = grade("preds.jsonl", "dataset", "123", str(out_dir))
    
    mock_swebench_main.assert_called_once()
    assert res == "report"
    assert not (out_dir / "test.123.json").exists()
    assert (out_dir / "test.456.json").exists()

def test_parse_results(tmp_path):
    (tmp_path / "test.123.json").write_text(json.dumps({
        "resolved_ids": ["a"],
        "unresolved_ids": ["b"],
        "error_ids": ["c"],
        "empty_patch_ids": ["d"]
    }))
    report = parse_results("123", str(tmp_path))
    assert report.total == 4
    assert report.resolved == 1
    assert report.per_instance["a"] == "resolved"
    assert report.per_instance["d"] == "unresolved"

def test_parse_results_fallback(tmp_path):
    # Missing JSON should fallback to _parse_per_instance_logs
    with mock.patch("eval.grader._parse_per_instance_logs") as mock_parse:
        mock_parse.return_value = "report"
        res = parse_results("123", str(tmp_path))
        assert res == "report"

def test_parse_per_instance_logs_empty(tmp_path):
    report = _parse_per_instance_logs("123", str(tmp_path))
    assert report.total == 0

def test_parse_per_instance_logs_with_data(tmp_path):
    log_dir = tmp_path / "logs" / "run_evaluation" / "123" / "model_x"
    # Valid resolved
    inst1 = log_dir / "inst1"
    inst1.mkdir(parents=True)
    (inst1 / "report.json").write_text(json.dumps({"inst1": {"resolved": True}}))
    # Valid unresolved
    inst2 = log_dir / "inst2"
    inst2.mkdir(parents=True)
    (inst2 / "report.json").write_text(json.dumps({"inst2": {"resolved": False}}))
    # Error (invalid JSON)
    inst3 = log_dir / "inst3"
    inst3.mkdir(parents=True)
    (inst3 / "report.json").write_text("{invalid")
    # Missing file
    inst4 = log_dir / "inst4"
    inst4.mkdir(parents=True)
    # File not a dir
    (tmp_path / "logs" / "run_evaluation" / "123" / "file.txt").write_text("x")
    
    # Run from the correct cwd so it finds "logs"
    with mock.patch("os.path.exists", side_effect=lambda p: True if "logs" in p else os.path.exists(p)):
        with mock.patch("os.listdir", side_effect=lambda p: ["model_x", "file.txt"] if p.endswith("123") else (["inst1", "inst2", "inst3", "inst4"] if p.endswith("model_x") else [])):
            with mock.patch("os.path.isdir", side_effect=lambda p: "model_x" in p):
                # We need to mock open, but it's easier to just temporarily chdir
                pass
                
    # Better: just set the CWD for the test
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    try:
        report = _parse_per_instance_logs("123", "out")
        assert report.total == 4
        assert report.resolved == 1
        assert report.unresolved == 1
        assert report.errored == 2
        assert report.per_instance["inst1"] == "resolved"
        assert report.per_instance["inst2"] == "unresolved"
        assert report.per_instance["inst3"] == "error"
        assert report.per_instance["inst4"] == "error"
    finally:
        os.chdir(cwd)
