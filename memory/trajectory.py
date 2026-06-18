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


def save_trajectory(instance_id: str, history: List[Dict[str, Any]], metrics: Dict[str, Any], custom_run_dir: str = None) -> str:
    """Save the agent's interaction history to a JSONL file."""
    base_dir = custom_run_dir if custom_run_dir else RUNS_DIR
    run_dir = os.path.join(base_dir, instance_id)
    os.makedirs(run_dir, exist_ok=True)
    
    # Save the full trajectory history
    traj_path = os.path.join(run_dir, "trajectory.jsonl")
    with open(traj_path, "w", encoding="utf-8") as f:
        for msg in history:
            f.write(json.dumps(msg) + "\n")
            
    # Save metrics JSON for easy parsing
    metrics_path = os.path.join(run_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        
    print(f"[Logging] Trajectory saved to {traj_path}")
    
    # Also log to SQLite if using the default dir
    if not custom_run_dir:
        try:
            init_db()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO metrics 
                (instance_id, timestamp, status, total_steps, total_tokens, cost, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                instance_id,
                timestamp,
                metrics.get("status", "unknown"),
                metrics.get("total_steps", 0),
                metrics.get("total_tokens", 0),
                metrics.get("cost", 0.0),
                metrics.get("duration_seconds", 0.0)
            ))
            conn.commit()
            conn.close()
            print(f"[Logging] Metrics recorded to SQLite for instance {instance_id}")
        except Exception as e:
            print(f"[Logging] Failed to write to SQLite: {e}")
        
    return traj_path
