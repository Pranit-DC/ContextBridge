"""Install a release in a clean temporary environment and open its bundled UI without Node."""

import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="contextbridge-release-probe-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(ROOT / "dist/contextbridge-local.zip") as bundle:
            bundle.extractall(target)
        installation = target / "ContextBridge"
        environment = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("CONTEXTBRIDGE_", "COMPOSE_", "VIRTUAL_ENV"))
        }
        subprocess.run(
            [
                "uv",
                "sync",
                "--directory",
                str(installation),
                "--frozen",
                "--no-dev",
                "--extra",
                "product",
                "--python",
                "3.12",
            ],
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        code = """
from pathlib import Path
from fastapi.testclient import TestClient
from contextbridge.product.cli import prepare
from contextbridge.product.app import create_product_app
root=Path.cwd()
prepare(root)
with TestClient(create_product_app(root,port=18502),base_url='http://127.0.0.1:18502') as client:
    response=client.get('/')
    assert response.status_code==200
    assert 'ContextBridge' in response.text
    assert '/_next/static/' in response.text
    assert \"script-src 'self' 'sha256-\" in response.headers['content-security-policy']
assert not (root/'node_modules').exists()
assert not (root/'frontend').exists()
assert 'FORMATION_API_KEY' not in (root/'.env').read_text()
"""
        subprocess.run(
            ["uv", "run", "--directory", str(installation), "--no-sync", "python", "-c", code],
            env=environment,
            cwd=installation,
            check=True,
        )
    print("PASS: clean release installs and serves bundled UI without Node or provider keys")


if __name__ == "__main__":
    main()
