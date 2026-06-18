import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict

from config import RUNS_DIR

DB_PATH = os.path.join(RUNS_DIR, "metrics.db")


def init_db():
    os.makedirs(RUNS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            instance_id TEXT PRIMARY KEY,
            timestamp TEXT,
            status TEXT,
            total_steps INTEGER,
            total_tokens INTEGER,
            cost REAL,
            duration_seconds REAL
        )
    """)
    conn.commit()
    conn.close()


def append_trajectory_step(instance_id: str, step: Dict[str, Any]):
    """
    Appends a single step to the trajectory JSONL file.
    """
    os.makedirs(RUNS_DIR, exist_ok=True)
    instance_dir = os.path.join(RUNS_DIR, instance_id)
    os.makedirs(instance_dir, exist_ok=True)

    traj_path = os.path.join(instance_dir, "trajectory.jsonl")
    with open(traj_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(step) + "\n")


def dump_run_config(instance_id: str, config_data: Dict[str, Any]):
    """
    Dumps the configuration used for this run into the instance directory.
    """
    os.makedirs(RUNS_DIR, exist_ok=True)
    instance_dir = os.path.join(RUNS_DIR, instance_id)
    os.makedirs(instance_dir, exist_ok=True)

    config_path = os.path.join(instance_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


def save_metrics(instance_id: str, metrics: Dict[str, Any]):
    """
    Logs high-level metrics to SQLite.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = datetime.utcnow().isoformat()
    status = metrics.get("status", "unknown")
    total_steps = metrics.get("total_steps", 0)
    total_tokens = metrics.get("total_tokens", 0)
    cost = metrics.get("cost", 0.0)
    duration_seconds = metrics.get("duration_seconds", 0.0)

    cursor.execute(
        """
        INSERT OR REPLACE INTO metrics 
        (instance_id, timestamp, status, total_steps, total_tokens, cost, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (instance_id, timestamp, status, total_steps, total_tokens, cost, duration_seconds),
    )

    conn.commit()
    conn.close()

    print(f"[Logging] Metrics recorded to SQLite for instance {instance_id}")
