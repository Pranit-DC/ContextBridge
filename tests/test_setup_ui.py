from pathlib import Path

from scripts import setup_ui


def test_setup_launcher_uses_loopback_discards_inherited_model_keys_and_does_not_require_ai(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / ".env"
    path.write_text("# Providers are intentionally not configured yet.\n")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_API_KEY", "private-inherited-model-key")
    calls = []
    monkeypatch.setattr(
        setup_ui.subprocess, "call", lambda command, **kw: calls.append((command, kw)) or 0
    )
    assert setup_ui.main(["--env-file", str(path), "--port", "8517"]) == 0
    command, arguments = calls[0]
    assert "127.0.0.1" in command and "8517" in command
    assert Path(command[command.index("run") + 1]).parts[-2:] == ("local_ui", "app.py")
    assert "CONTEXTBRIDGE_FORMATION_API_KEY" not in arguments["env"]
    assert arguments["env"]["CONTEXTBRIDGE_LOCAL_ENV_FILE"] == str(path)
    assert arguments["env"]["CONTEXTBRIDGE_LOCAL_ALLOW_RESTART"] == "false"
    assert "private-inherited-model-key" not in repr(calls)


def test_setup_does_not_follow_symlink_or_launch_with_missing_custom_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        setup_ui.subprocess, "call", lambda *a, **k: (_ for _ in ()).throw(AssertionError())
    )
    assert setup_ui.main(["--env-file", str(tmp_path / "missing.env")]) == 1
