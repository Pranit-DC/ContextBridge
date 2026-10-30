"""Disposable managed-key Docker probe. Synthetic vault/keys, no provider requests."""

import json
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from contextbridge.local_ui.settings import KeyChange, Preferences, SettingsError
from contextbridge.product.services import Services
from contextbridge.product.settings import ProductSettings
from contextbridge.product.vault import NativeVault

ROOT = Path(__file__).resolve().parents[1]


class ProbeBackend:
    value = None

    def get_password(self, *_):
        return self.value

    def set_password(self, *args):
        self.value = args[-1]


def wait(check, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except (httpx.HTTPError, ValueError, KeyError, SettingsError):
            pass
        time.sleep(1)
    raise RuntimeError("PRODUCT_STACK_NOT_READY")


def main():
    # A fresh random project owns only its own containers, network and disposable volumes.
    project = "contextbridge-product-probe-" + secrets.token_hex(5)
    commands = []
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        directory = Path(temporary)
        for name in (
            "pyproject.toml",
            "uv.lock",
            "Dockerfile",
            "alembic.ini",
            "compose.product.yaml",
        ):
            shutil.copy2(ROOT / name, directory / name)
        shutil.copytree(
            ROOT / "src", directory / "src", ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copytree(
            ROOT / "migrations",
            directory / "migrations",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (directory / ".dockerignore").write_text(".env\n.contextbridge\n")
        compose = (
            (ROOT / "compose.yaml")
            .read_text()
            .replace('"127.0.0.1:8000:8000"', '"127.0.0.1:0:8000"')
            .replace('"127.0.0.1:${CONTEXTBRIDGE_DB_PORT:-5433}:5432"', '"127.0.0.1:0:5432"')
        )
        # Containers can communicate with each other, but have no provider egress.
        compose += "\nnetworks:\n  default:\n    internal: true\n"
        (directory / "compose.yaml").write_text(compose)
        token, password = secrets.token_hex(24), secrets.token_hex(24)
        (directory / ".env").write_text(
            f"CONTEXTBRIDGE_DB_PASSWORD='{password}'\nCONTEXTBRIDGE_API_TOKEN='{token}'\n"
            f"CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://contextbridge:{password}@127.0.0.1/unused_test'\n"
        )
        store = ProductSettings(
            directory / ".env", vault=NativeVault(directory, backend=ProbeBackend())
        )
        provider_key = "synthetic-runtime-provider-key-" + secrets.token_hex(12)
        public = store.save(
            "initial",
            Preferences(processing=True, groq_free_confirmed=True),
            KeyChange(action="replace", value=provider_key),
            KeyChange(),
        )

        def run(args, **kwargs):
            # Set an explicit unique Compose project; never infer the real repository project.
            if "compose" in args:
                position = args.index("--project-name")
                args[position + 1] = project
            commands.append(args)
            if "logs" in args:
                kwargs["stderr"] = subprocess.STDOUT
            return subprocess.run(args, **kwargs)

        services = Services(store, directory, runner=run)
        services.project = project
        try:
            services.apply(public["revision"])

            def status():
                raw = services.command(
                    [
                        "exec",
                        "--no-TTY",
                        "api",
                        "python",
                        "-c",
                        "import json,os,urllib.request; "
                        "r=urllib.request.Request('http://127.0.0.1:8000/v1/status', "
                        "headers={'Authorization':'Bearer '+"
                        "os.environ['CONTEXTBRIDGE_API_TOKEN']}); "
                        "print(json.dumps(json.load(urllib.request.urlopen(r,timeout=3))))",
                    ],
                    capture=True,
                )
                return json.loads(raw)

            wait(lambda: status()["extraction_configured"] is True)
            for service in ("api", "worker", "scheduler"):
                container = services.command(["ps", "-q", service], capture=True).decode().strip()
                inspected = subprocess.run(
                    ["docker", "--host", services.local_endpoint(), "inspect", container],
                    capture_output=True,
                    check=True,
                ).stdout
                assert provider_key.encode() not in inspected
                assert "/run/contextbridge" in json.loads(inspected)[0]["HostConfig"]["Tmpfs"]
            newer = store.save(
                public["revision"],
                Preferences(processing=True, groq_free_confirmed=True),
                KeyChange(action="replace", value="synthetic-rotated-provider-key-12345"),
                KeyChange(),
            )
            services.apply(newer["revision"])
            wait(lambda: status()["extraction_configured"] is True)
            services.apply("offline", offline=True)
            wait(lambda: status()["extraction_configured"] is False)
            assert provider_key not in (directory / ".env").read_text()
            print(
                "PASS: managed startup, runtime provider loading, private tmpfs, "
                "empty provider environment, rotation/recreation, no provider egress"
            )
        except Exception:
            for service in ("api", "worker", "scheduler"):
                try:
                    logs = services.command(
                        ["logs", "--no-color", "--tail", "35", service], capture=True
                    ).decode()
                    for secret in (
                        provider_key,
                        token,
                        password,
                        "synthetic-rotated-provider-key-12345",
                    ):
                        logs = logs.replace(secret, "[redacted synthetic credential]")
                    print(logs[-8000:])
                except Exception:
                    print("Probe diagnostics unavailable")
            raise
        finally:
            services.command(["down", "--volumes", "--remove-orphans"], timeout=60)


if __name__ == "__main__":
    main()
