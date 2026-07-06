import argparse
import logging
import subprocess
import sys
from pathlib import Path

from src import auth, pipeline, report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="YouTube upload automation")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Run one-time OAuth2 browser login and cache the token")
    sub.add_parser("run", help="Process one queued video end to end")
    report_parser = sub.add_parser("report", help="Generate visualization report")
    report_parser.add_argument("--output", default=None, help="Output PNG path")
    sub.add_parser("dashboard", help="Launch interactive Streamlit dashboard")

    args = parser.parse_args()

    if args.command == "login":
        auth.get_credentials()
        print("Login successful, token cached.")
    elif args.command == "run":
        processed = pipeline.run_once()
        print("Processed a video." if processed else "Nothing to process.")
    elif args.command == "report":
        path = report.generate(args.output)
        print(f"Report written to {path}")
    elif args.command == "dashboard":
        dashboard_path = Path(__file__).parent / "src" / "dashboard.py"
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])


if __name__ == "__main__":
    main()
