import sqlite3
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config, db


def generate(output_path: str | None = None) -> str:
    db.init_db()
    output_path = output_path or str(config.REPORT_DIR / "report.png")

    with db.connect() as conn:
        conn.row_factory = sqlite3.Row
        runs = conn.execute("SELECT * FROM runs ORDER BY started_at").fetchall()
        stages = conn.execute("SELECT * FROM stage_timings").fetchall()

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # 1. Success vs failure counts
    status_counts = defaultdict(int)
    for r in runs:
        status_counts[r["status"]] += 1
    axes[0].bar(status_counts.keys(), status_counts.values(), color=["#4caf50", "#f44336", "#ff9800"])
    axes[0].set_title("Run outcomes")

    # 2. Uploads per day
    per_day = defaultdict(int)
    for r in runs:
        if r["status"] == "success":
            day = datetime.fromtimestamp(r["started_at"]).strftime("%Y-%m-%d")
            per_day[day] += 1
    days = sorted(per_day)
    axes[1].plot(days, [per_day[d] for d in days], marker="o")
    axes[1].set_title("Successful uploads per day")
    axes[1].tick_params(axis="x", rotation=45)

    # 3. Average duration per stage
    stage_durations = defaultdict(list)
    for s in stages:
        stage_durations[s["stage"]].append(s["duration_seconds"])
    stage_names = list(stage_durations)
    avg_durations = [sum(v) / len(v) for v in stage_durations.values()]
    axes[2].barh(stage_names, avg_durations, color="#2196f3")
    axes[2].set_title("Avg stage duration (s)")

    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return output_path
