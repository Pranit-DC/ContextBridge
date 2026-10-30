"""Container-local credential handoff. Secret bytes enter only through stdin."""

import argparse
import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

DIRECTORY = Path("/run/contextbridge")
CREDENTIALS = DIRECTORY / "providers.json"
COMMANDS = {
    "api": ["uvicorn", "contextbridge.main:app", "--host", "0.0.0.0", "--port", "8000"],
    "worker": [
        "celery",
        "-A",
        "contextbridge.background.celery_app:app",
        "worker",
        "--loglevel=INFO",
        "--concurrency=2",
    ],
    "scheduler": ["python", "-m", "contextbridge.background.celery_app"],
}


def managed_enabled(value=None):
    value = os.environ.get("CONTEXTBRIDGE_MANAGED_CREDENTIALS", "false") if value is None else value
    return (
        value is True
        or isinstance(value, str)
        and value.strip().lower() in {"1", "true", "yes", "on"}
    )


def require_tmpfs():
    rows = Path("/proc/self/mountinfo").read_text().splitlines()
    for row in rows:
        parts = row.split()
        if parts[4] == str(DIRECTORY) and parts[parts.index("-") + 1] == "tmpfs":
            return
    raise ValueError("Managed credential handoff requires its private tmpfs mount")


def read_credentials(path=CREDENTIALS):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as file:
        metadata = os.fstat(file.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise ValueError("Private credentials unavailable")
        raw = file.read(16_385)
    if len(raw) > 16_384:
        raise ValueError("Private credentials unavailable")
    data = json.loads(raw)
    if set(data) != {"groq", "cloudflare"}:
        raise ValueError("Private credentials unavailable")
    from contextbridge.local_ui.settings import KeyChange

    return {key: KeyChange().replacement(value) for key, value in data.items()}


def inject(raw, directory=DIRECTORY):
    if len(raw) > 16_384 or directory.is_symlink():
        raise ValueError
    directory.mkdir(mode=0o700, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        read_credentials(Path(name))
        os.replace(name, directory / "providers.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=[*COMMANDS, "inject"])
    args = parser.parse_args()
    if args.role == "inject":
        try:
            require_tmpfs()
            inject(sys.stdin.buffer.read(16_385))
        except Exception:
            return 2
        return 0
    while not CREDENTIALS.is_file():
        time.sleep(0.25)
    try:
        require_tmpfs()
        read_credentials()
    except Exception:
        return 2
    # Bootstrap never copies provider values into environment variables.
    os.execvp(COMMANDS[args.role][0], COMMANDS[args.role])


if __name__ == "__main__":
    raise SystemExit(main())
