import asyncio
import json
import os
import re
import site
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from scripts import setup_local


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "Context Bridge café"
    root.mkdir()
    python = setup_local.interpreter_path(root)
    python.parent.mkdir(parents=True)
    python.touch()
    return root


def test_setup_creates_matching_private_settings_and_native_configs(checkout, monkeypatch):
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", "unrelated-shell-token-that-is-long-enough")
    messages = setup_local.prepare(checkout, "team project café", 5440)
    env = (checkout / ".env").read_text(encoding="utf-8")
    token = setup_local.ServiceToken(_env_file=checkout / ".env").api_token.get_secret_value()
    password = re.search(r"CONTEXTBRIDGE_DB_PASSWORD=([0-9a-f]+)", env)[1]
    assert re.fullmatch("[0-9a-f]{64}", token)
    assert re.fullmatch("[0-9a-f]{64}", password)
    assert token != password
    assert "@localhost:5440/contextbridge" in env
    assert "CONTEXTBRIDGE_DB_PORT=5440" in env
    assert setup_local.ServiceToken(
        _env_file=checkout / ".env.mcp"
    ).api_token.get_secret_value() == (token)
    adapter = (checkout / ".env.mcp").read_text(encoding="utf-8")
    assert password not in adapter
    assert "DATABASE" not in adapter
    assert token not in "\n".join(messages)
    assert password not in "\n".join(messages)

    output = checkout / ".contextbridge"
    codex = tomllib.loads((output / "codex-mcp.toml").read_text(encoding="utf-8"))["mcp_servers"][
        "contextbridge"
    ]
    claude = json.loads((output / "claude-mcp.json").read_text(encoding="utf-8"))["mcpServers"][
        "contextbridge"
    ]
    for name, config in (("codex", codex), ("claude-code", claude)):
        assert config["command"] == str(setup_local.interpreter_path(checkout))
        assert config["args"] == [
            "-m",
            "contextbridge.mcp_adapter.cli",
            "--env-file",
            str(checkout / ".env.mcp"),
            "--project-id",
            "team project café",
            "--agent-id",
            name,
        ]
        assert token not in str(config)
        assert password not in str(config)
    if os.name != "nt":
        assert (checkout / ".env").stat().st_mode & 0o777 == 0o600
        assert (checkout / ".env.mcp").stat().st_mode & 0o777 == 0o600


def test_rerun_preserves_credentials_ports_and_custom_adapter(checkout):
    setup_local.prepare(checkout, "first", 5433)
    original_env = (checkout / ".env").read_bytes()
    adapter = b"# Custom settings must survive\nCONTEXTBRIDGE_API_URL=http://localhost:9000\n"
    (checkout / ".env.mcp").write_bytes(adapter)
    setup_local.prepare(checkout, "second", 5441)
    assert (checkout / ".env").read_bytes() == original_env
    assert (checkout / ".env.mcp").read_bytes() == adapter
    codex = (checkout / ".contextbridge" / "codex-mcp.toml").read_text(encoding="utf-8")
    assert '"second"' in codex
    assert '"first"' not in codex


@pytest.mark.parametrize("token", ["short", "replace-with-a-random-token-at-least-32-characters"])
def test_invalid_existing_token_is_not_replaced(checkout, token):
    original = f"CONTEXTBRIDGE_API_TOKEN={token}\n"
    (checkout / ".env").write_text(original, encoding="utf-8")
    with pytest.raises(ValueError):
        setup_local.prepare(checkout, "project", 5433)
    assert (checkout / ".env").read_text(encoding="utf-8") == original
    assert not (checkout / ".env.mcp").exists()


def test_missing_virtual_environment_does_not_create_settings(tmp_path):
    with pytest.raises(ValueError, match="uv sync"):
        setup_local.prepare(tmp_path, "project", 5433)
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("project,port", [(" ", 5433), ("x" * 129, 5433), ("p", 80), ("p", 65536)])
def test_invalid_inputs_do_not_create_settings(checkout, project, port):
    with pytest.raises(ValueError):
        setup_local.prepare(checkout, project, port)
    assert not (checkout / ".env").exists()


def test_codex_toml_preserves_windows_backslashes_and_spaces():
    config = setup_local.mcp_config(
        r"C:\Users\A Person\Context Bridge\.venv\Scripts\python.exe",
        r"C:\Users\A Person\Context Bridge\.env.mcp",
        'project with "quotes"',
        "codex",
    )
    parsed = tomllib.loads(setup_local.codex_toml(config))["mcp_servers"]["contextbridge"]
    assert parsed["command"] == config["command"]
    assert parsed["args"] == config["args"]


def test_cli_errors_do_not_echo_credentials(monkeypatch, capsys):
    def fail(*args):
        raise OSError("private-credential-must-not-appear")

    monkeypatch.setattr(setup_local, "prepare", fail)
    monkeypatch.setattr(sys, "argv", ["setup_local.py"])
    assert setup_local.main() == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Setup failed" in captured.err
    assert "private-credential" not in captured.err


def test_generated_config_launches_real_mcp_from_an_unrelated_directory(tmp_path):
    # Exercise native Windows/Linux process creation with spaces and Unicode in the env path.
    root = tmp_path / "Context Bridge café"
    root.mkdir()
    python = setup_local.interpreter_path(root)
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")], check=True)
    # Reuse installed test dependencies without downloading into the disposable venv.
    packages = (
        root / ".venv" / "Lib" / "site-packages"
        if os.name == "nt"
        else root
        / ".venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    (packages / "test-dependencies.pth").write_text(
        # Process dependency .pth files too: pywin32 needs its DLL/bootstrap paths on Windows.
        "\n".join(
            [
                *(
                    f"import site; site.addsitedir({directory!r})"
                    for directory in site.getsitepackages()
                ),
                str(Path(__file__).resolve().parents[1] / "src"),
            ]
        ),
        encoding="utf-8",
    )
    setup_local.prepare(root, "project café", 5433)
    config = json.loads((root / ".contextbridge" / "claude-mcp.json").read_text(encoding="utf-8"))[
        "mcpServers"
    ]["contextbridge"]
    assert config["command"] == str(python)

    async def scenario():
        async with Client(
            StdioServerParameters(command=config["command"], args=config["args"], cwd=tmp_path),
            read_timeout_seconds=10,
        ) as client:
            assert len((await client.list_tools()).tools) == 6

    asyncio.run(scenario())
