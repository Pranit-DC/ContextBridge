"""Fixed Compose operations; never accept arbitrary executable paths or commands from HTTP."""

import json
import os
import re
import subprocess
import threading
from pathlib import Path

from contextbridge.local_ui.settings import SettingsError

CONSUMERS = ("api", "worker", "scheduler")


class Services:
    def __init__(self, settings, root, *, runner=subprocess.run, endpoint=None):
        self.settings, self.root, self.runner = settings, Path(root).resolve(), runner
        self.endpoint = endpoint
        self.project = (
            re.sub(r"[^a-z0-9_-]", "", self.root.name.lower()).lstrip("-_") or "contextbridge"
        )
        self.lock = threading.Lock()
        self.phase = "idle"
        self.applied_revision = None

    def local_endpoint(self):
        if self.endpoint is None:
            endpoint = os.environ.get("DOCKER_HOST")
            if not endpoint:
                try:
                    result = self.runner(
                        ["docker", "context", "inspect"],
                        stdout=subprocess.PIPE,
                        env={
                            k: v
                            for k, v in os.environ.items()
                            if not k.startswith(("CONTEXTBRIDGE_", "COMPOSE_"))
                        },
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                        check=False,
                    )
                    if result.returncode:
                        raise ValueError
                    endpoint = json.loads(result.stdout)[0]["Endpoints"]["docker"]["Host"]
                except (OSError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired):
                    raise SettingsError(
                        "Select a local Docker Engine or Docker Desktop context."
                    ) from None
            if not endpoint.startswith(("unix://", "npipe://")):
                raise SettingsError(
                    "Remote Docker endpoints are not supported by this local product."
                )
            self.endpoint = endpoint
        return self.endpoint

    def verify_ownership(self):
        try:
            prefix = ["docker", "--host", self.local_endpoint()]
            result = self.runner(
                [
                    *prefix,
                    "ps",
                    "-aq",
                    "--filter",
                    f"label=com.docker.compose.project={self.project}",
                ],
                stdout=subprocess.PIPE,
                env={
                    k: v
                    for k, v in os.environ.items()
                    if not k.startswith(("CONTEXTBRIDGE_", "COMPOSE_"))
                },
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            if result.returncode:
                raise ValueError
            ids = result.stdout.decode().split()
            if ids:
                result = self.runner(
                    [*prefix, "inspect", *ids],
                    stdout=subprocess.PIPE,
                    env={
                        k: v
                        for k, v in os.environ.items()
                        if not k.startswith(("CONTEXTBRIDGE_", "COMPOSE_"))
                    },
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
                if result.returncode:
                    raise ValueError
                rows = json.loads(result.stdout)
                if not isinstance(rows, list) or len(rows) != len(ids):
                    raise ValueError
                for row in rows:
                    labels = row["Config"]["Labels"]
                    directory = labels.get("com.docker.compose.project.working_dir", "")
                    if not directory or Path(directory).resolve() != self.root:
                        raise ValueError
            else:
                result = self.runner(
                    [
                        *prefix,
                        "volume",
                        "ls",
                        "-q",
                        "--filter",
                        f"label=com.docker.compose.project={self.project}",
                    ],
                    stdout=subprocess.PIPE,
                    env={
                        k: v
                        for k, v in os.environ.items()
                        if not k.startswith(("CONTEXTBRIDGE_", "COMPOSE_"))
                    },
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
                if result.returncode or result.stdout.strip():
                    raise SettingsError(
                        "Existing volumes need ownership review. "
                        "Start the original installation first; "
                        "no volumes were changed."
                    )
        except SettingsError:
            raise
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            raise SettingsError(
                "This Docker project belongs to another installation or cannot be inspected."
            ) from None

    def command(self, args, *, record=None, stdin=None, capture=False, timeout=180):
        if not (self.root / "compose.yaml").is_file():
            raise SettingsError("This installation is missing its Docker service files.")
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("CONTEXTBRIDGE_", "COMPOSE_"))
            and k not in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
        }
        # Legacy .env may still contain provider keys. Never pass them through Docker env.
        if record is not None:
            env.update(self.settings.nonsecret_environment(record))
        env.update(CONTEXTBRIDGE_FORMATION_API_KEY="", CONTEXTBRIDGE_EMBEDDING_API_KEY="")
        try:
            result = self.runner(
                [
                    "docker",
                    "--host",
                    self.local_endpoint(),
                    "compose",
                    "--project-name",
                    self.project,
                    "--file",
                    str(self.root / "compose.yaml"),
                    "--file",
                    str(self.root / "compose.product.yaml"),
                    "--env-file",
                    str(self.settings.legacy.path),
                    "--profile",
                    "workers",
                    *args,
                ],
                cwd=self.root,
                env=env,
                input=stdin,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
            if result.returncode:
                raise ValueError
            return result.stdout if capture else None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise SettingsError(
                "Docker operation failed. Check Docker and retry; volumes are preserved."
            ) from None

    def status(self):
        try:
            raw = self.command(["ps", "--all", "--format", "json"], capture=True, timeout=5)
            text = raw.decode() if isinstance(raw, bytes) else raw
            if len(text) > 65_536:
                raise ValueError
            rows = (
                json.loads(text)
                if text.strip().startswith("[")
                else [json.loads(line) for line in text.splitlines() if line.strip()]
            )
            return {
                "docker_available": True,
                "phase": self.phase,
                "applied_revision": self.applied_revision,
                "services": [
                    {
                        **{k: row.get(k, "") for k in ("Service", "State", "Health")},
                        "ExitCode": row.get("ExitCode"),
                    }
                    for row in rows
                ],
            }
        except (SettingsError, ValueError, TypeError):
            return {
                "docker_available": False,
                "phase": self.phase,
                "applied_revision": self.applied_revision,
                "services": [],
            }

    def pause(self):
        self.verify_ownership()
        self.command(["stop", *CONSUMERS])
        self.applied_revision = None

    def apply(self, revision, *, offline=False):
        if not self.lock.acquire(blocking=False):
            raise SettingsError("Another service operation is running.")
        try:
            from contextbridge.local_ui.settings import Preferences
            from contextbridge.product.vault import VaultRecord

            record = (
                VaultRecord(revision="offline", preferences=Preferences())
                if offline
                else self.settings.record()
            )
            if not offline and record.revision != revision:
                raise SettingsError("Settings changed. Reload before applying.")
            self.settings.runtime(record)  # Validate before stopping any service.
            self.settings.activate()
            self.phase = "applying"
            self.pause()
            self.command(
                ["up", "--build", "--detach", "--force-recreate", *CONSUMERS], record=record
            )
            for service in CONSUMERS:
                if not offline and self.settings.record().revision != revision:
                    raise SettingsError("Settings changed during startup. Apply again.")
                self.command(
                    [
                        "exec",
                        "--no-TTY",
                        service,
                        "python",
                        "-m",
                        "contextbridge.product.bootstrap",
                        "inject",
                    ],
                    record=record,
                    stdin=json.dumps(
                        {"groq": record.groq, "cloudflare": record.cloudflare}
                    ).encode(),
                )
            if not offline and self.settings.record().revision != revision:
                raise SettingsError("Settings changed during startup. Apply again.")
            self.applied_revision = record.revision
            self.phase = "applied"
        except Exception:
            self.phase = "needs_attention"
            # A partial handoff must never leave some consumers running with old credentials.
            try:
                self.pause()
            except SettingsError:
                pass
            raise
        finally:
            self.lock.release()

    def stop(self):
        if not self.lock.acquire(blocking=False):
            raise SettingsError("Another service operation is running.")
        try:
            self.verify_ownership()
            self.command(["stop"])
            self.phase, self.applied_revision = "stopped", None
        finally:
            self.lock.release()
