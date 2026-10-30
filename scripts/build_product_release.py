"""Build a credential-free local release with prebuilt web assets; Node is build-time only."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "Dockerfile",
    ".dockerignore",
    "compose.yaml",
    "compose.product.yaml",
    "alembic.ini",
    "docs/local-product.md",
    "docs/evidence-time-v2.md",
    "docs/memory-compaction.md",
    "docs/agent-integration.md",
)


def build(output):
    web = ROOT / "src/contextbridge/product/web"
    if not (web / "index.html").is_file() or not (web / "csp.json").is_file():
        raise RuntimeError("Build the frontend before packaging the product")
    paths = [ROOT / name for name in FILES]
    for directory in ("src", "migrations"):
        paths.extend(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file()
            and not p.is_symlink()
            and "__pycache__" not in p.parts
            and p.name != ".gitignore"
            and p.suffix not in {".pyc", ".pyo"}
        )
    # Explicit trees only: never include local state, dotenv files, vaults or developer tools.
    manifest = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(paths):
            bundle.write(path, "ContextBridge/" + str(path.relative_to(ROOT)))
        bundle.writestr("ContextBridge/release-manifest.json", json.dumps(manifest, indent=2))
    print(f"Built {output.name}: {len(manifest)} files, no local configuration")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/contextbridge-local.zip")
    build(parser.parse_args().output)


if __name__ == "__main__":
    main()
