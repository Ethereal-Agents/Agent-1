import os
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
    assert cursor.fetchone()[0] == 'metrics'
    conn.close()


def test_save_trajectory(mock_db):
    test_runs_dir, test_db_path = mock_db
    
    instance_id = "test_123"
    history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]
    metrics = {
        "status": "success",
        "total_steps": 2,
        "total_tokens": 100,
        "cost": 0.05,
        "duration_seconds": 1.5
    }
    
    # Actually run save_trajectory
    trajectory.save_trajectory(instance_id, history, metrics)
    
    # 1. Verify JSONL
    traj_path = test_runs_dir / instance_id / "trajectory.jsonl"
    assert traj_path.exists()
    
    with open(traj_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == history[0]
        assert json.loads(lines[1]) == history[1]
        
    # 2. Verify SQLite DB
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM metrics WHERE instance_id=?", (instance_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    # row format: instance_id, timestamp, status, total_steps, total_tokens, cost, duration_seconds
    assert row[0] == instance_id
    assert isinstance(row[1], str)  # timestamp
    assert row[2] == "success"
    assert row[3] == 2
    assert row[4] == 100
    assert row[5] == 0.05
    assert row[6] == 1.5


def test_save_trajectory_default_metrics(mock_db):
    test_runs_dir, test_db_path = mock_db
    
    instance_id = "test_default"
    history = []
    metrics = {}  # Empty metrics
    
    trajectory.save_trajectory(instance_id, history, metrics)
    
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT status, total_steps, total_tokens, cost, duration_seconds FROM metrics WHERE instance_id=?", (instance_id,))
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == "unknown"
    assert row[1] == 0
    assert row[2] == 0
    assert row[3] == 0.0
    assert row[4] == 0.0
