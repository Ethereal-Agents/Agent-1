import os
import sys
import json
from unittest import mock
import pytest

from eval.run_eval import _load_eval_config, _resolve_instances, main, _save_results_json, _load_results_json, _print_summary, _print_run_status
from eval.models import EvalConfig, TaskResult, GradeReport

def test_load_eval_config(tmp_path):
    class Args:
        dataset = "d"
        split = "s"
        model = "m"
        max_workers_inference = 1
        max_workers_grading = 1
        timeout = 10
        output_dir = "o"
        namespace = "n"
        budget_warn = 1.0
        resume = True
    cfg = _load_eval_config(Args())
    assert cfg.dataset == "d"
    assert cfg.split == "s"
    assert cfg.model == "m"
    assert cfg.resume is True

@mock.patch("eval.dataset.filter_by_instance_ids")
@mock.patch("eval.dataset.filter_by_tier")
def test_resolve_instances(mock_filter_tier, mock_filter_ids):
    class Args:
        instance_ids = "a,b"
        tier = None
    _resolve_instances(Args(), [], "base")
    mock_filter_ids.assert_called_once()
    
    class Args2:
        instance_ids = None
        tier = 10
    _resolve_instances(Args2(), [], "base")
    mock_filter_tier.assert_called_once()
    
    class Args3:
        instance_ids = None
        tier = None
    res = _resolve_instances(Args3(), [1,2], "base")
    assert res == [1,2]

def test_save_load_results(tmp_path):
    r = TaskResult("a", "m", "p", "s", 1, 1, 1.0, 1.0, "t")
    _save_results_json([r], str(tmp_path))
    assert (tmp_path / "results.json").exists()
    
    loaded = _load_results_json(str(tmp_path))
    assert len(loaded) == 1
    assert loaded[0].instance_id == "a"
    
def test_load_results_empty(tmp_path):
    assert _load_results_json(str(tmp_path)) == []

def test_print_summary(capsys):
    from eval.models import EvalMetrics, StatSummary
    m = EvalMetrics("run", 1.0, 1, 1, 0, 0, StatSummary(1,1,1,1), StatSummary(1,1,1,1), StatSummary(1,1,1,1), StatSummary(1,1,1,1), {})
    _print_summary(m)
    assert "RESULTS" in capsys.readouterr().out

@mock.patch("eval.grader.parse_results")
def test_print_run_status(mock_parse, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "trajectories" / "i1").mkdir(parents=True)
    (out / "trajectories" / "i1" / "result.json").write_text(json.dumps({"model_patch": "p"}))
    (out / "trajectories" / "i2").mkdir(parents=True)
    (out / "trajectories" / "i2" / "result.json").write_text(json.dumps({"model_patch": ""}))
    
    mock_parse.return_value = GradeReport("r", 2, 1, 1, 0, 0.5, {"i1": "resolved"})
    _print_run_status(str(out), [{"instance_id": "i1"}, {"instance_id": "i2"}, {"instance_id": "i3"}], "r")
    mock_parse.assert_called_once()

@mock.patch("eval.grader.write_predictions")
@mock.patch("eval.grader.grade")
@mock.patch("eval.run_eval.sys.exit")
@mock.patch("eval.run_eval._print_run_status")
@mock.patch("eval.dataset.load_swe_bench")
@mock.patch("eval.run_eval._resolve_instances")
@mock.patch("eval.runner.run_batch")
@mock.patch("eval.reporter.compute_metrics")
@mock.patch("eval.reporter.generate_report")
@mock.patch("eval.run_eval._print_summary")
def test_main_full(mock_ps, mock_gr, mock_cm, mock_rb, mock_ri, mock_lsb, mock_status, mock_exit, mock_grade, mock_wp):
    mock_lsb.return_value = []
    mock_ri.return_value = [{"instance_id": "a"}]
    mock_rb.return_value = [TaskResult("a", "m", "p", "s", 1, 1, 1.0, 1.0, "t")]
    mock_grade.return_value = GradeReport("r", 1, 1, 0, 0, 1.0, {"a": "resolved"})
    
    test_args = ["run_eval.py", "--dataset", "d", "--run-id", "r"]
    with mock.patch("sys.argv", test_args):
        main()
        
    mock_rb.assert_called_once()
    mock_grade.assert_called_once()
    mock_gr.assert_called_once()

@mock.patch("eval.run_eval.sys.exit", side_effect=SystemExit)
@mock.patch("eval.run_eval._print_run_status")
@mock.patch("eval.dataset.load_swe_bench")
@mock.patch("eval.run_eval._resolve_instances")
def test_main_status(mock_ri, mock_lsb, mock_status, mock_exit):
    mock_ri.return_value = [{"instance_id": "a", "repo": "r", "problem_statement": "p"}]
    test_args = ["run_eval.py", "--status", "--run-id", "r"]
    with mock.patch("sys.argv", test_args):
        with pytest.raises(SystemExit):
            main()
    mock_status.assert_called_once()
    mock_exit.assert_called_once_with(0)

@mock.patch("eval.grader.write_predictions")
@mock.patch("eval.run_eval.sys.exit", side_effect=SystemExit)
@mock.patch("eval.dataset.load_swe_bench")
@mock.patch("eval.run_eval._resolve_instances")
@mock.patch("eval.runner.run_batch")
def test_main_inference_only(mock_rb, mock_ri, mock_lsb, mock_exit, mock_wp):
    mock_ri.return_value = [{"instance_id": "a"}]
    test_args = ["run_eval.py", "--inference-only", "--run-id", "r"]
    with mock.patch("sys.argv", test_args):
        main()
    mock_rb.assert_called_once()

@mock.patch("eval.grader.grade")
@mock.patch("eval.run_eval.sys.exit", side_effect=SystemExit)
def test_main_grade_only(mock_exit, mock_grade, tmp_path):
    (tmp_path / "preds.jsonl").write_text("")
    test_args = ["run_eval.py", "--grade-only", "--predictions", str(tmp_path / "preds.jsonl"), "--run-id", "r", "--output-dir", str(tmp_path)]
    with mock.patch("sys.argv", test_args):
        main()
    mock_grade.assert_called_once()

def test_main_errors():
    with mock.patch("sys.argv", ["run_eval.py", "--grade-only"]):
        with pytest.raises(SystemExit):
            main()
    
    with mock.patch("sys.argv", ["run_eval.py", "--inference-only", "--grade-only"]):
        with pytest.raises(SystemExit):
            main()
