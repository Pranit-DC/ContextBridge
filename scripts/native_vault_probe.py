"""Probe the real OS vault using an isolated synthetic entry; always attempt cleanup."""

import json
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from contextbridge.product.vault import NativeVault, VaultRecord


def main():
    with tempfile.TemporaryDirectory(prefix="contextbridge-native-vault-probe-") as directory:
        vault = NativeVault(Path(directory))
        try:
            assert vault.read() is None
            first = VaultRecord(groq="synthetic-native-vault-probe-123456789")
            vault.write(first)
            assert vault.read().encoded() == first.encoded()
            second = VaultRecord(cloudflare="synthetic-native-vault-rotation-123456")
            vault.write(second)
            assert vault.read().encoded() == second.encoded()
            vault.operation("delete")
            # Real application settings endpoint plus real native vault. Docker is
            # deliberately absent here; the separate egress-blocked stack probe owns it.
            from fastapi.testclient import TestClient

            from contextbridge.product.app import create_product_app
            from contextbridge.product.settings import ProductSettings

            root = Path(directory)
            (root / ".env").write_text(
                "CONTEXTBRIDGE_API_TOKEN='synthetic-vault-probe-token-1234567890'\n"
                "CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://test:test@127.0.0.1/native_test'\n"
            )
            store = ProductSettings(root / ".env", vault=vault)
            services = SimpleNamespace(
                lock=threading.Lock(), status=lambda: {"docker_available": False}
            )
            app = create_product_app(root, settings=store, services=services)
            with TestClient(app, base_url="http://127.0.0.1:8501") as client:
                launch = app.state.launch_url.split("launch=")[1]
                headers = {"Origin": "http://127.0.0.1:8501"}
                session = client.post(
                    "/api/local/v1/session", json={"launch": launch}, headers=headers
                )
                headers["X-CSRF-Token"] = session.json()["csrf"]
                result = client.put(
                    "/api/local/v1/config",
                    headers=headers,
                    json={
                        "revision": "initial",
                        "preferences": {},
                        "groq": {"action": "replace", "value": first.groq},
                    },
                )
                assert result.status_code == 200
                assert result.json()["groq_configured"]
                assert first.groq not in json.dumps(result.json())
                assert first.groq not in (root / ".env").read_text()
                assert store.record().groq == first.groq
        finally:
            if vault.read() is not None:
                vault.operation("delete")
        assert vault.read() is None
    print("PASS: native storage/application save, read, replace, deletion; synthetic entry removed")


if __name__ == "__main__":
    main()
