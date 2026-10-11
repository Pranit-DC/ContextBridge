"""The administrative test runner must reject unsafe configuration before any database action."""

import importlib.util
from contextlib import nullcontext
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


def test_full_runner_isolates_test_database_and_does_not_auto_sign_in_viewer(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts" / "formation" / "run_checks.py"
    spec = importlib.util.spec_from_file_location("formation_checks_runner", path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(
        runner,
        "Settings",
        lambda: SimpleNamespace(
            database_url=SecretStr("postgresql+psycopg://sample:synthetic@127.0.0.1/application"),
            api_token=SecretStr("synthetic-service-token-not-for-viewer"),
        ),
    )
    monkeypatch.setattr(runner.secrets, "token_hex", lambda size: "abcdef012345")
    executed = []
    connection = SimpleNamespace(
        dialect=SimpleNamespace(identifier_preparer=SimpleNamespace(quote=lambda name: name)),
        exec_driver_sql=lambda sql: executed.append(sql),
    )
    engine = SimpleNamespace(connect=lambda: nullcontext(connection), dispose=lambda: None)
    monkeypatch.setattr(runner, "create_engine", lambda *args, **kwargs: engine)
    calls = []

    def run(command, **options):
        calls.append((command, options["env"]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", run)
    report = runner.ElementTree.fromstring('<testsuites><testsuite skipped="0"/></testsuites>')
    monkeypatch.setattr(
        runner.ElementTree, "parse", lambda path: SimpleNamespace(getroot=lambda: report)
    )
    assert runner.main() == 0
    assert executed == ["CREATE DATABASE contextbridge_om_abcdef012345_test"]
    assert len(calls) == 5
    for command, environment in calls:
        assert environment["CONTEXTBRIDGE_DATABASE_URL"].endswith("_test")
        assert (
            environment["CONTEXTBRIDGE_TEST_DATABASE_URL"]
            == environment["CONTEXTBRIDGE_DATABASE_URL"]
        )
        if command[2] == "pytest":
            assert "CONTEXTBRIDGE_API_TOKEN" not in environment
        else:
            assert (
                environment["CONTEXTBRIDGE_API_TOKEN"] == "synthetic-service-token-not-for-viewer"
            )
