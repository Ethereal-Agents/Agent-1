import json
import sqlite3

import pytest

from memory import trajectory


@pytest.fixture
def mock_db(tmp_path, monkeypatch):
    test_runs_dir = tmp_path / "runs"
    test_db_path = test_runs_dir / "metrics.db"

    # Monkeypatch the paths in the trajectory module so we don't pollute the real DB
    monkeypatch.setattr(trajectory, "RUNS_DIR", str(test_runs_dir))
    monkeypatch.setattr(trajectory, "DB_PATH", str(test_db_path))

    return test_runs_dir, test_db_path


def test_init_db(mock_db):
    test_runs_dir, test_db_path = mock_db

    # Ensure it creates the DB and table
    trajectory.init_db()

    assert test_runs_dir.exists()
    assert test_db_path.exists()

    # Verify the table schema
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'")
    assert cursor.fetchone()[0] == "metrics"
    conn.close()


def test_append_trajectory_step(mock_db):
    test_runs_dir, test_db_path = mock_db
    instance_id = "test_123"
    step1 = {"role": "user", "content": "hello"}
    step2 = {"role": "assistant", "content": "world"}

    trajectory.append_trajectory_step(instance_id, step1)
    trajectory.append_trajectory_step(instance_id, step2)

    traj_path = test_runs_dir / instance_id / "trajectory.jsonl"
    assert traj_path.exists()

    with open(traj_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == step1
        assert json.loads(lines[1]) == step2


def test_dump_run_config(mock_db):
    test_runs_dir, test_db_path = mock_db
    instance_id = "test_config_123"
    config_data = {"test": "data", "nested": {"key": "value"}}

    trajectory.dump_run_config(instance_id, config_data)

    config_path = test_runs_dir / instance_id / "config.json"
    assert config_path.exists()

    with open(config_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        assert loaded == config_data


def test_save_metrics(mock_db):
    test_runs_dir, test_db_path = mock_db
    instance_id = "test_123"
    metrics = {
        "status": "success",
        "total_steps": 2,
        "total_tokens": 100,
        "cost": 0.05,
        "duration_seconds": 1.5,
    }

    trajectory.save_metrics(instance_id, metrics)

    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM metrics WHERE instance_id=?", (instance_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == instance_id
    assert isinstance(row[1], str)
    assert row[2] == "success"
    assert row[3] == 2
    assert row[4] == 100
    assert row[5] == 0.05
    assert row[6] == 1.5


def test_save_metrics_default_metrics(mock_db):
    test_runs_dir, test_db_path = mock_db
    instance_id = "test_default"
    metrics = {}

    trajectory.save_metrics(instance_id, metrics)

    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, total_steps, total_tokens, cost, duration_seconds FROM metrics WHERE instance_id=?",
        (instance_id,),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "unknown"
    assert row[1] == 0
    assert row[2] == 0
    assert row[3] == 0.0
    assert row[4] == 0.0
