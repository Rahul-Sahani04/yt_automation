import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    status TEXT NOT NULL DEFAULT 'running',
    video_id TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS stage_timings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    stage TEXT NOT NULL,
    duration_seconds REAL NOT NULL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def start_run(source_file: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (source_file, started_at, status) VALUES (?, ?, 'running')",
            (source_file, time.time()),
        )
        return cur.lastrowid


def record_stage(run_id: int, stage: str, duration_seconds: float):
    with connect() as conn:
        conn.execute(
            "INSERT INTO stage_timings (run_id, stage, duration_seconds) VALUES (?, ?, ?)",
            (run_id, stage, duration_seconds),
        )


def finish_run(run_id: int, status: str, video_id: str | None = None, error: str | None = None):
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, video_id = ?, error = ? WHERE id = ?",
            (time.time(), status, video_id, error, run_id),
        )
