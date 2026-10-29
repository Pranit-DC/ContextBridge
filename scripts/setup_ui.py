"""Open the local workspace without requiring provider credentials or a running API."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--project-id")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-service-restart", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535.")
    path = args.env_file.absolute()
    if not path.exists() and path == ROOT / ".env":
        from setup_local import prepare

        try:
            prepare(ROOT, args.project_id or "contextbridge", 5433)
        except (ValueError, OSError):
            print("Local setup unavailable. Run uv sync --frozen --all-extras first.")
            return 1
    if not path.is_file() or path.is_symlink():
        print("Choose an existing private settings file, or use the default local setup.")
        return 1
    env = {k: v for k, v in os.environ.items() if not k.startswith("CONTEXTBRIDGE_")}
    env["CONTEXTBRIDGE_LOCAL_ENV_FILE"] = str(path)
    if args.project_id:
        env["CONTEXTBRIDGE_PROJECT_ID"] = args.project_id
    env["CONTEXTBRIDGE_LOCAL_START_SETTINGS"] = "true"
    env["CONTEXTBRIDGE_LOCAL_ALLOW_RESTART"] = str(
        not args.no_service_restart and path.parent.resolve() == ROOT
    ).lower()
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "src/contextbridge/local_ui/app.py"),
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(args.port),
            "--browser.gatherUsageStats",
            "false",
            "--client.toolbarMode",
            "minimal",
            "--client.showErrorDetails",
            "false",
            "--theme.base",
            "light",
            "--theme.primaryColor",
            "#136d76",
            "--theme.backgroundColor",
            "#fcfcfd",
            "--theme.secondaryBackgroundColor",
            "#f3f6f8",
            "--theme.textColor",
            "#172b3a",
        ],
        cwd=ROOT,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
