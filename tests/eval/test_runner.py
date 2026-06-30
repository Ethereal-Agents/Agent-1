import os
import json
from unittest import mock
import pytest

from eval.runner import _build_swebench_image, _get_docker_client, _extract_patch, run_single_task, _infer_exit_reason, _budget_check, run_batch
from eval.models import EvalConfig

@mock.patch("swebench.harness.docker_build.build_instance_image")
@mock.patch("swebench.harness.run_evaluation.make_test_spec")
@mock.patch("eval.runner._get_docker_client")
def test_build_swebench_image(mock_client, mock_make, mock_build):
    class DummySpec:
        instance_image_key = "img"
        repo_script_list = ["pip install a", "other cmd"]
    spec = DummySpec()
    mock_make.return_value = spec
    
    # test astropy path
    res = _build_swebench_image({"repo": "astropy"}, "ns")
    assert res == "img"
    # verify patches
    assert any("setuptools<70" in c for c in spec.repo_script_list)
    assert any("--no-build-isolation" in c for c in spec.repo_script_list)
    assert not any("--no-use-pep517" in c for c in spec.repo_script_list)

@mock.patch("docker.from_env")
def test_get_docker_client(mock_from_env):
    mock_client = mock.MagicMock()
    mock_from_env.return_value = mock_client
    res = _get_docker_client()
    assert res == mock_client

@mock.patch("docker.from_env")
def test_get_docker_client_fails(mock_from_env):
    mock_from_env.side_effect = Exception("Fail")
    with pytest.raises(EnvironmentError):
        _get_docker_client()

@mock.patch("subprocess.run")
def test_extract_patch(mock_run):
    mock_res = mock.MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "diff text"
    mock_run.return_value = mock_res
    
    assert _extract_patch("c", "commit") == "diff text"
    
    mock_res.stdout = "   "
    assert _extract_patch("c", "commit") is None
    
    mock_res.returncode = 1
    assert _extract_patch("c", "commit") is None

@mock.patch("eval.runner._get_docker_client")
@mock.patch("eval.runner._build_swebench_image")
@mock.patch("eval.runner._extract_patch")
@mock.patch("agent.loop.Agent")
@mock.patch("tools.registry.initialize_tools")
@mock.patch("tools.environment.DockerEnvironment")
def test_run_single_task(mock_env, mock_init, mock_agent_cls, mock_extract, mock_build, mock_client, tmp_path):
    mock_build.return_value = "img"
    
    mock_docker = mock.MagicMock()
    mock_container = mock.MagicMock()
    mock_container.id = "cid"
    mock_container.short_id = "cid_short"
    mock_docker.containers.run.return_value = mock_container
    mock_client.return_value = mock_docker
    
    mock_agent = mock.MagicMock()
    mock_agent.step_count = 5
    mock_agent.cumulative_tokens = 100
    mock_agent.cumulative_cost = 1.5
    mock_agent_cls.return_value = mock_agent
    
    mock_extract.return_value = "patch"
    
    cfg = EvalConfig(model="m")
    instance = {"instance_id": "i1", "base_commit": "c", "repo": "r", "problem_statement": "p"}
    
    res = run_single_task(instance, cfg, str(tmp_path))
    assert res.exit_reason == "submitted"
    assert res.model_patch == "patch"
    
    # test resume logic
    cfg.resume = True
    res_path = tmp_path / "trajectories" / "i1" / "result.json"
    assert res_path.exists()
    
    # run again, should return saved
    res2 = run_single_task(instance, cfg, str(tmp_path))
    assert res2.exit_reason == "submitted"
    
    # corrupted json
    res_path.write_text("invalid")
    res3 = run_single_task(instance, cfg, str(tmp_path))
    assert res3.exit_reason == "submitted" # runs again

@mock.patch("eval.runner._get_docker_client")
@mock.patch("eval.runner._build_swebench_image")
def test_run_single_task_error(mock_build, mock_client, tmp_path):
    mock_build.side_effect = Exception("Crash")
    cfg = EvalConfig(model="m")
    instance = {"instance_id": "i2", "base_commit": "c", "repo": "r"}
    res = run_single_task(instance, cfg, str(tmp_path))
    assert res.exit_reason == "error"

def test_infer_exit_reason():
    agent = mock.MagicMock()
    from config import MAX_STEPS
    agent.step_count = MAX_STEPS + 10 # > default max
    assert _infer_exit_reason(agent) == "max_steps"
    agent.step_count = 10
    assert _infer_exit_reason(agent) == "submitted"

def test_budget_check(capsys):
    cfg = EvalConfig(budget_warn_threshold=10.0, budget_warn_interval_pct=[50, 100])
    _budget_check(1.0, cfg)
    assert capsys.readouterr().out == ""
    _budget_check(5.0, cfg)
    assert "BUDGET WARNING" in capsys.readouterr().out
    _budget_check(11.0, cfg)
    assert "BUDGET WARNING" in capsys.readouterr().out
    
    cfg.budget_warn_threshold = 0
    _budget_check(10.0, cfg)

@mock.patch("swebench.harness.docker_build.build_env_images")
@mock.patch("eval.runner._get_docker_client")
@mock.patch("eval.runner.run_single_task")
def test_run_batch_seq(mock_rst, mock_client, mock_build, tmp_path):
    mock_rst.return_value = mock.MagicMock(total_cost=1.0)
    cfg = EvalConfig(max_workers_inference=1)
    res = run_batch([{"instance_id": "i1"}], cfg, str(tmp_path))
    assert len(res) == 1
    mock_rst.assert_called_once()

@mock.patch("swebench.harness.docker_build.build_env_images")
@mock.patch("eval.runner._get_docker_client")
@mock.patch("eval.runner.concurrent.futures.ProcessPoolExecutor")
def test_run_batch_parallel(mock_ppe, mock_client, mock_build, tmp_path):
    mock_executor = mock.MagicMock()
    mock_ppe.return_value.__enter__.return_value = mock_executor
    # simulate futures returning
    mock_future1 = mock.MagicMock()
    mock_future1.result.return_value = mock.MagicMock(total_cost=1.0)
    mock_future2 = mock.MagicMock()
    mock_future2.result.return_value = mock.MagicMock(total_cost=1.0)
    
    # We have to mock as_completed to return these futures
    with mock.patch("eval.runner.concurrent.futures.as_completed", return_value=[mock_future1, mock_future2]):
        # Mock executor.submit to return futures that we can index
        mock_executor.submit.side_effect = [mock_future1, mock_future2]
        
        cfg = EvalConfig(max_workers_inference=2)
        res = run_batch([{"instance_id": "i1"}, {"instance_id": "i2"}], cfg, str(tmp_path))
        assert len(res) == 2
    
@mock.patch("swebench.harness.docker_build.build_env_images")
@mock.patch("eval.runner._get_docker_client")
@mock.patch("eval.runner.concurrent.futures.ProcessPoolExecutor")
def test_run_batch_parallel_error(mock_ppe, mock_client, mock_build, tmp_path):
    mock_executor = mock.MagicMock()
    mock_ppe.return_value.__enter__.return_value = mock_executor
    mock_future = mock.MagicMock()
    mock_future.result.side_effect = Exception("Fail")
    
    with mock.patch("eval.runner.concurrent.futures.as_completed", return_value=[mock_future]):
        mock_executor.submit.return_value = mock_future
        cfg = EvalConfig(max_workers_inference=2)
        res = run_batch([{"instance_id": "i1"}], cfg, str(tmp_path))
        assert len(res) == 0
