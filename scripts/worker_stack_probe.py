"""Disposable full Compose restart probe. Synthetic providers; no development data touched."""

import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "contextbridge-worker-probe"


def wait_for(check, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("STACK_NOT_READY")


def main():
    # Refuse to claim or remove a pre-existing stack, even if its name matches this probe.
    existing = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    if existing.stdout.strip():
        raise RuntimeError("PROBE_STACK_ALREADY_EXISTS")
    for suffix in ["postgres_data", "redis_data"]:
        found = subprocess.run(
            ["docker", "volume", "inspect", f"{PROJECT}_{suffix}"], capture_output=True
        )
        if found.returncode == 0:
            raise RuntimeError("PROBE_VOLUME_ALREADY_EXISTS")
    with tempfile.TemporaryDirectory(prefix="contextbridge-worker-probe-") as temporary:
        directory = Path(temporary)
        token, password = secrets.token_hex(24), secrets.token_hex(24)
        env = directory / "probe.env"
        env.write_text(
            f"CONTEXTBRIDGE_DB_PASSWORD={password}\nCONTEXTBRIDGE_API_TOKEN={token}\n"
            "CONTEXTBRIDGE_DEVELOPER_ID=worker-probe\nCONTEXTBRIDGE_DB_PORT=55436\n"
            "CONTEXTBRIDGE_CAPTURE_PROJECT_ID=contextbridge\n"
            "CONTEXTBRIDGE_WORKER_FACTORY=tests.background.worker_factory:make\n",
            encoding="utf-8",
        )
        database_url = (
            f"postgresql+psycopg://contextbridge:{password}@db:5432/contextbridge_worker_probe_test"
        )
        # Build a whitelisted temporary context: the real Docker context excludes tests.
        # This also avoids host bind permissions/SELinux and never copies .env or .git.
        context = directory / "test-image"
        context.mkdir()
        for name in ["pyproject.toml", "uv.lock", "alembic.ini"]:
            shutil.copyfile(ROOT / name, context / name)
        for name in ["src", "migrations", "docs/team-plan/fixtures"]:
            shutil.copytree(
                ROOT / name, context / name, ignore=shutil.ignore_patterns("__pycache__")
            )
        for name in [
            "tests/__init__.py",
            "tests/background/__init__.py",
            "tests/background/worker_factory.py",
            "tests/engine/__init__.py",
            "tests/engine/fakes.py",
        ]:
            target = context / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        common = {"environment": {"CONTEXTBRIDGE_DATABASE_URL": database_url}}
        worker = {
            "environment": {"CONTEXTBRIDGE_DATABASE_URL": database_url, "PYTHONPATH": "/app"},
            "build": {
                "context": str(context),
                "dockerfile_inline": (ROOT / "Dockerfile").read_text().replace("$", "$$")
                + "\nCOPY tests /app/tests\n"
                "COPY docs/team-plan/fixtures /app/docs/team-plan/fixtures\n",
            },
        }
        # JSON is valid YAML. The ports override tag isolates the API from the real local stack.
        override = directory / "probe.yaml"
        fragments = [
            "services:",
            "  db:",
            "    environment:",
            "      POSTGRES_DB: contextbridge_worker_probe_test",
        ]
        for name, body in [
            ("migrate", common),
            ("api", common),
            ("worker", worker),
            ("scheduler", common),
        ]:
            fragments.append(f"  {name}: " + json.dumps(body))
        # API needs an additional YAML tag; combine its environment and isolated port mapping.
        fragments[fragments.index("  api: " + json.dumps(common))] = (
            "  api:\n    environment: "
            + json.dumps(common["environment"])
            + '\n    ports: !override ["127.0.0.1:18036:8000"]'
        )
        override.write_text("\n".join(fragments) + "\n", encoding="utf-8")
        command = [
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "--env-file",
            str(env),
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
            "--profile",
            "workers",
        ]
        with (directory / "docker.log").open("w") as log:

            def compose(*args):
                result = subprocess.run(
                    [*command, *args],
                    cwd=ROOT,
                    stdout=log,
                    stderr=log,
                    env={
                        **os.environ,
                        "CONTEXTBRIDGE_API_TOKEN": token,
                        "CONTEXTBRIDGE_DB_PASSWORD": password,
                        "CONTEXTBRIDGE_DB_PORT": "55436",
                        "CONTEXTBRIDGE_DEVELOPER_ID": "worker-probe",
                        "CONTEXTBRIDGE_CAPTURE_PROJECT_ID": "contextbridge",
                        "CONTEXTBRIDGE_WORKER_FACTORY": "tests.background.worker_factory:make",
                    },
                )
                if result.returncode:
                    # A diagnostic contains only build output for this synthetic stack.
                    log.flush()
                    (
                        Path(tempfile.gettempdir()) / "contextbridge-worker-probe-docker.log"
                    ).write_text((directory / "docker.log").read_text(), encoding="utf-8")
                    raise RuntimeError("COMPOSE_OPERATION_FAILED")

            try:
                print("Building isolated worker stack", flush=True)
                compose("up", "--build", "--detach")
                with httpx.Client(
                    base_url="http://127.0.0.1:18036",
                    timeout=3,
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    wait_for(lambda: client.get("/health/ready").status_code == 200)
                    event = json.loads(
                        (ROOT / "docs/team-plan/fixtures/captured-event.json").read_text()
                    )
                    event.update(
                        event_id=str(uuid4()),
                        occurred_at=(datetime.now(UTC) - timedelta(seconds=10)).isoformat(),
                    )
                    accepted = client.post("/v1/interactions", json=event)
                    assert accepted.status_code == 202
                    job_id = accepted.json()["job_id"]

                    def result():
                        response = client.get(f"/v1/jobs/{job_id}")
                        if response.status_code != 200:
                            return None
                        payload = response.json()
                        if payload["status"] in {"failed", "cancelled", "deferred"}:
                            raise RuntimeError(f"WORK_NOT_SUCCEEDED: {payload['reason_codes']}")
                        return payload if payload["status"] == "succeeded" else None

                    memory_id = wait_for(result)["memory_ids"][0]
                    before = client.get(f"/v1/memories/{memory_id}").json()
                    corrected = client.put(
                        f"/v1/memories/{memory_id}",
                        json={
                            "expected_version": 1,
                            "content": "Keep the synthetic PostgreSQL backup policy.",
                            "source": before["memory"]["version"]["source"],
                        },
                    )
                    assert corrected.status_code == 200
                    print("Restarting all services and checking preserved versions", flush=True)
                    compose("restart")
                    wait_for(lambda: client.get("/health/ready").status_code == 200)
                    inspected = client.get(f"/v1/memories/{memory_id}").json()
                    assert inspected["memory"]["current_version"] == 2
                    assert len(inspected["history"]) == 2
                    assert client.delete(f"/v1/memories/{memory_id}").status_code == 204
                    assert client.post("/v1/interactions", json=event).status_code == 409
                    compose("restart")
                    wait_for(lambda: client.get("/health/ready").status_code == 200)
                    assert client.get(f"/v1/memories/{memory_id}").status_code == 404
                    assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "cancelled"
                    print(
                        "PASS: ingestion, correction, restart, forgetting, and replay fence",
                        flush=True,
                    )
            finally:
                # Only this newly created disposable project and its own volumes are removed.
                compose("down", "--volumes", "--remove-orphans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
