import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List

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


def save_trajectory(instance_id: str, history: List[Dict[str, Any]], metrics: Dict[str, Any]):
    """
    Saves the full history to a JSONL file and logs high-level metrics to SQLite.
    Follows the SWE-agent and OpenHands pattern of making raw trajectories highly portable.
    """
    os.makedirs(RUNS_DIR, exist_ok=True)

    # 1. Save Trajectory as JSONL
    instance_dir = os.path.join(RUNS_DIR, instance_id)
    os.makedirs(instance_dir, exist_ok=True)

    traj_path = os.path.join(instance_dir, "trajectory.jsonl")
    with open(traj_path, "w", encoding="utf-8") as f:
        for step in history:
            f.write(json.dumps(step) + "\n")

    # 2. Save Metrics to SQLite for dashboarding
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

    print(f"[Logging] Trajectory saved to {traj_path}")
    print(f"[Logging] Metrics recorded to SQLite for instance {instance_id}")
