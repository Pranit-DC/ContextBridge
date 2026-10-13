"""Start the configured ContextBridge V1 services and viewer on Linux."""

import argparse
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

from contextbridge.config import Settings

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "scripts" / "start_v1.py"


def wait_for_service(token, project, *, timeout=60, client=None):
    """Confirm service readiness and the exact project binding, without calling models."""
    deadline = time.monotonic() + timeout
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        headers={"Authorization": f"Bearer {token}"},
        timeout=3,
        trust_env=False,
        follow_redirects=False,
        transport=client,
    ) as connection:
        while time.monotonic() < deadline:
            try:
                ready = connection.get("/health/ready")
                if ready.status_code in (401, 403):
                    return "The running service rejected the configured access token."
                if ready.status_code == 200:
                    status = connection.get("/v1/status")
                    if status.status_code == 200:
                        configuration = status.json()
                        if not isinstance(configuration, dict):
                            return "The service returned invalid configuration."
                        if configuration.get("capture_project_id") != project:
                            return (
                                "The running service uses a different project. "
                                "Restart it with this project ID."
                            )
                        if not all(
                            configuration.get(field) is True
                            for field in ("extraction_configured", "embeddings_configured")
                        ):
                            return (
                                "AI processing or meaning search is not configured. "
                                "Check the provider settings."
                            )
                        return None
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(1)
    return "The memory service did not become ready. Check Docker service status before retrying."


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def viewer_ready(address):
    try:
        with httpx.Client(timeout=1, trust_env=False, follow_redirects=False) as connection:
            result = connection.get(address + "/_stcore/health")
            return result.status_code == 200 and result.text.strip() == "ok"
    except httpx.HTTPError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--free-groq-confirmed", action="store_true")
    parser.add_argument("--action", choices=("start", "check", "stop"), default="start")
    parser.add_argument("--viewer-port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    args.project_id = args.project_id.strip()
    if not 1 <= len(args.project_id) <= 128:
        parser.error("Enter a project ID containing 1 to 128 characters.")
    if not sys.platform.startswith("linux"):
        parser.error("Use the existing V1 start guide on Windows; this launcher is for Linux.")
    if not 1024 <= args.viewer_port <= 65535:
        parser.error("Choose a viewer port from 1024 to 65535.")
    env_file = args.env_file.resolve()
    common = [
        sys.executable,
        str(START),
        "--env-file",
        str(env_file),
        "--project-id",
        args.project_id,
    ]
    if args.free_groq_confirmed:
        common.append("--free-groq-confirmed")
    if args.action == "stop":
        return subprocess.call(
            ["docker", "compose", "--env-file", str(env_file), "--profile", "workers", "stop"],
            cwd=ROOT,
        )
    result = subprocess.call([*common, "--action", "check"], cwd=ROOT)
    if result or args.action == "check":
        return result
    result = subprocess.call([*common, "--action", "start"], cwd=ROOT)
    if result:
        print(
            "Services did not start. Resolve the reported Docker error before opening the viewer."
        )
        return result
    settings = Settings(_env_file=env_file)
    failure = wait_for_service(settings.api_token.get_secret_value(), args.project_id)
    if failure:
        print(failure)
        return 1
    address = f"http://127.0.0.1:{args.viewer_port}"
    print(f"ContextBridge V1 is ready for project {args.project_id}. Open {address}", flush=True)
    if listening(args.viewer_port):
        if not viewer_ready(address):
            print("The viewer port belongs to another service. Choose --viewer-port 8502.")
            return 1
        print("A viewer is already running. Select the project shown above in its sidebar.")
        if not args.no_browser:
            webbrowser.open(address)
        return 0
    # Reuse the V1 configuration, then pass only viewer credentials to the viewer process.
    sys.path.insert(0, str(ROOT / "scripts"))
    from start_v1 import environment

    configured = environment(
        env_file, free_confirmed=args.free_groq_confirmed, project=args.project_id
    )
    env = {
        key: value
        for key, value in configured.items()
        if not key.startswith("CONTEXTBRIDGE_")
        or key in {"CONTEXTBRIDGE_API_TOKEN", "CONTEXTBRIDGE_PROJECT_ID"}
    }
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT / "src/contextbridge/inspection/app.py"),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(args.viewer_port),
        "--server.headless",
        "true",
    ]
    child = subprocess.Popen(command, cwd=ROOT, env=env)
    try:
        deadline = time.monotonic() + 20
        while child.poll() is None and time.monotonic() < deadline:
            if viewer_ready(address):
                print("Viewer ready. Keep this terminal open. Ctrl+C stops the viewer.", flush=True)
                if not args.no_browser:
                    webbrowser.open(address)
                return child.wait()
            time.sleep(0.25)
        print("The viewer did not start. Check the displayed startup error.")
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
