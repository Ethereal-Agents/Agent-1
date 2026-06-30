import os
import sys
import json
import pytest
from unittest import mock

# eval.dataset.py: 31
from eval.dataset import filter_by_tier
def test_dataset_missing_tier():
    with pytest.raises(FileNotFoundError):
        filter_by_tier([], "does_not_exist.json")

# eval.grader.py: 57-58
from eval.grader import grade
@mock.patch("swebench.harness.run_evaluation.main")
@mock.patch("eval.grader.parse_results")
def test_grader_delete_error(mock_pr, mock_sm, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    f = out / "t.123.json"
    f.write_text("x")
    with mock.patch("os.remove", side_effect=Exception("mock")):
        grade("p", "d", "123", str(out)) # should silently pass exception

# eval.grader.py: 96, 105-111
from eval.grader import parse_results
def test_parse_results_current_dir(tmp_path):
    # simulate file in "." but missing in output_dir, and shutil.move fails
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    try:
        (tmp_path / "test.123.json").write_text('{"resolved_ids": []}')
        with mock.patch("shutil.move", side_effect=Exception("move fail")):
            parse_results("123", "dummy_out")
    finally:
        os.chdir(cwd)

# eval.reporter.py: 167, 210
from eval.reporter import _write_markdown_report
from eval.models import EvalMetrics, StatSummary, GradeReport, TaskResult
def test_write_markdown_report_tags(tmp_path):
    m = EvalMetrics("run", 1.0, 1, 1, 0, 0, StatSummary(1,1,1,1), StatSummary(1,1,1,1), StatSummary(1,1,1,1), StatSummary(1,1,1,1), {})
    r = TaskResult("a", "m", "p", "s", 1, 1, 1.0, 1.0, "t")
    gr = GradeReport("r", 1, 1, 0, 0, 1.0, {}) # missing 'a'
    tags = [{"instance_id": "a", "grade": "unresolved", "tag": "test_tag"}]
    _write_markdown_report(m, [r], gr, tags, str(tmp_path))

# eval.run_eval.py: 169
from eval.run_eval import main
def test_main_mutually_exclusive():
    with mock.patch("sys.argv", ["run_eval.py", "--inference-only", "--grade-only", "--predictions", "dummy.jsonl"]):
        with pytest.raises(SystemExit):
            main()

# eval.run_eval.py: 197-198, 216-217
@mock.patch("eval.run_eval.sys.exit", side_effect=SystemExit)
@mock.patch("eval.dataset.load_swe_bench", return_value=[])
def test_main_no_instances(mock_lsb, mock_exit):
    with mock.patch("sys.argv", ["run_eval.py", "--status"]):
        with pytest.raises(SystemExit):
            main()
    with mock.patch("sys.argv", ["run_eval.py"]):
        with pytest.raises(SystemExit):
            main()

# eval.run_eval.py: 331-332, 348
from eval.run_eval import _print_run_status
@mock.patch("eval.grader.parse_results")
def test_print_run_status_exceptions(mock_pr, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    i = out / "trajectories" / "i"
    i.mkdir(parents=True)
    f = i / "result.json"
    f.write_text("invalid json")
    mock_pr.return_value = GradeReport("r", 1, 1, 0, 0, 1.0, {"i": "resolved"})
    _print_run_status(str(out), [{"instance_id": "i"}], "123")

# eval.runner.py: 144
from eval.runner import run_single_task
from eval.models import EvalConfig
@mock.patch("eval.runner._build_swebench_image", side_effect=Exception)
def test_runner_resume_clear_trajectory(mock_bld, tmp_path):
    cfg = EvalConfig(model="m", resume=True)
    out = tmp_path / "out"
    out.mkdir()
    i = out / "trajectories" / "i1"
    i.mkdir(parents=True)
    traj = i / "trajectory.jsonl"
    traj.write_text("old data")
    run_single_task({"instance_id": "i1"}, cfg, str(out))
    assert traj.read_text() == ""

# eval.runner.py: 228-229
@mock.patch("eval.runner._get_docker_client")
@mock.patch("eval.runner._build_swebench_image")
def test_runner_container_stop_error(mock_bld, mock_client, tmp_path):
    mock_bld.return_value = "img"
    mock_docker = mock.MagicMock()
    mock_container = mock.MagicMock()
    mock_container.stop.side_effect = Exception("Stop failed")
    mock_docker.containers.run.return_value = mock_container
    mock_client.return_value = mock_docker
    
    cfg = EvalConfig(model="m")
    # trigger an exception in loop to reach finally block
    with mock.patch("tools.environment.DockerEnvironment", side_effect=Exception):
        run_single_task({"instance_id": "i1", "repo": "r", "base_commit": "c", "problem_statement": "p"}, cfg, str(tmp_path))
