"""The administrative test runner must reject unsafe configuration before any database action."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///must-not-create.db",
        "postgresql+psycopg://sample:must-not-display@remote.example/contextbridge",
        "invalid-url-with-must-not-display",
    ],
)
def test_invalid_or_remote_configuration_cannot_create_a_database(monkeypatch, capsys, url):
    path = Path(__file__).resolve().parents[2] / "scripts" / "formation" / "run_checks.py"
    spec = importlib.util.spec_from_file_location("formation_checks_runner", path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(
        runner,
        "Settings",
        lambda: SimpleNamespace(database_url=SecretStr(url)),
    )

    def uncalled(*args, **kwargs):
        pytest.fail("Unsafe configuration must not connect, create a DB, or launch tests")

    monkeypatch.setattr(runner, "create_engine", uncalled)
    monkeypatch.setattr(runner.subprocess, "run", uncalled)
    assert runner.main() == 1
    assert "must-not-display" not in capsys.readouterr().out
