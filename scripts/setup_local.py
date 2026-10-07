"""Prepare private local settings and native MCP paths on Linux or Windows."""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceToken(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXTBRIDGE_", extra="ignore", env_file_encoding="utf-8-sig"
    )
    api_token: SecretStr = Field(min_length=32)

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        # Read this checkout's file, never an unrelated shell/CI token.
        return (dotenv_settings,)


def write_new_private_file(path: Path, content: str) -> None:
    # Exclusive creation prevents accidentally replacing an existing password/token.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)


def interpreter_path(root: Path) -> Path:
    # Do not resolve the executable symlink: the path must stay inside the venv.
    relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return root / ".venv" / relative


def mcp_config(command: str, env_file: str, project_id: str, agent: str) -> dict:
    return {
        "command": command,
        "args": [
            "-m",
            "contextbridge.mcp_adapter.cli",
            "--env-file",
            env_file,
            "--project-id",
            project_id,
            "--agent-id",
            agent,
        ],
    }


def codex_toml(config: dict) -> str:
    # JSON string escaping also gives valid TOML basic strings, including Windows backslashes.
    return (
        "[mcp_servers.contextbridge]\n"
        f"command = {json.dumps(config['command'], ensure_ascii=False)}\n"
        f"args = {json.dumps(config['args'], ensure_ascii=False)}\n"
        "startup_timeout_sec = 10\n"
        "tool_timeout_sec = 30\n"
    )


def prepare(root: Path, project_id: str, db_port: int) -> list[str]:
    root = root.resolve()
    python = interpreter_path(root)
    if not python.is_file():
        raise ValueError("Run uv sync --frozen --python 3.12 in the checkout first.")
    if not project_id.strip() or len(project_id) > 128:
        raise ValueError("Project ID must contain 1–128 characters.")
    if not 1024 <= db_port <= 65535:
        raise ValueError("Database host port must be between 1024 and 65535.")

    messages = []
    service_file = root / ".env"
    if not service_file.exists():
        password = secrets.token_hex(32)
        token = secrets.token_hex(32)
        write_new_private_file(
            service_file,
            "# Private local settings. Never commit this file.\n"
            f"CONTEXTBRIDGE_API_TOKEN={token}\n"
            f"CONTEXTBRIDGE_DB_PASSWORD={password}\n"
            f"CONTEXTBRIDGE_DB_PORT={db_port}\n"
            "CONTEXTBRIDGE_DATABASE_URL=postgresql+psycopg://contextbridge:"
            f"{password}@localhost:{db_port}/contextbridge\n"
            "CONTEXTBRIDGE_DEVELOPER_ID=local-developer\n",
        )
        messages.append("Created .env with separate random API token and database password.")
    else:
        messages.append("Kept existing .env unchanged (including its database port).")

    try:
        token = ServiceToken(_env_file=service_file).api_token.get_secret_value()
    except ValidationError as error:
        raise ValueError("Set a valid API token of at least 32 characters in .env.") from error
    if token.startswith("replace-with"):
        raise ValueError("Replace the API token placeholder in .env before running setup.")

    adapter_file = root / ".env.mcp"
    if not adapter_file.exists():
        # Quote the token when copying it into dotenv; generated tokens contain only hex digits.
        write_new_private_file(
            adapter_file,
            "# Private adapter settings; no database credentials.\n"
            "CONTEXTBRIDGE_API_URL=http://127.0.0.1:8000\n"
            f"CONTEXTBRIDGE_API_TOKEN={json.dumps(token, ensure_ascii=False)}\n",
        )
        messages.append("Created .env.mcp using the service's API token.")
    else:
        messages.append("Kept existing .env.mcp unchanged; its token must match the service.")

    output = root / ".contextbridge"
    output.mkdir(exist_ok=True)
    codex = mcp_config(str(python), str(adapter_file), project_id, "codex")
    claude = mcp_config(str(python), str(adapter_file), project_id, "claude-code")
    (output / "codex-mcp.toml").write_text(codex_toml(codex), encoding="utf-8", newline="\n")
    (output / "claude-mcp.json").write_text(
        json.dumps({"mcpServers": {"contextbridge": {"type": "stdio", **claude}}}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    messages.append("Generated native agent paths in .contextbridge/ (no credentials included).")
    messages.append(
        "Agent registration: follow docs/agent-integration.md for your operating system."
    )
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default="contextbridge")
    parser.add_argument(
        "--db-port", type=int, default=5433, help="Used only when creating a new .env"
    )
    args = parser.parse_args()
    try:
        messages = prepare(Path(__file__).resolve().parents[1], args.project_id, args.db_port)
    except (OSError, ValueError):
        # Do not echo validation exceptions, file contents, or credentials.
        print(
            "Setup failed. Run uv sync first; check file access, the API token in .env, "
            "project ID (1–128 characters), and port (1024–65535). "
            "Existing settings were not replaced.",
            file=sys.stderr,
        )
        return 1
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
