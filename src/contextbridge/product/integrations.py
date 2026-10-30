"""Project-scoped, explicit Codex hook changes; never touch another integration."""

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from contextbridge.local_ui.settings import SettingsError

MODULE = "contextbridge.capture_adapters.codex_hook"


def workspace_path(value):
    try:
        root = Path(value).expanduser()
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise ValueError
        root = root.resolve(strict=True)
        for part in (root / ".codex", root / ".contextbridge"):
            if part.is_symlink():
                raise ValueError
        return root
    except (OSError, ValueError):
        raise SettingsError(
            "Choose an existing absolute workspace directory without linked settings."
        ) from None


def hook_state(workspace):
    path = workspace_path(workspace) / ".codex" / "hooks.json"
    try:
        if path.is_symlink():
            raise ValueError
        if not path.exists():
            return {}, path
        if path.stat().st_size > 131_072:
            raise ValueError
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
            raise ValueError
        return data, path
    except (OSError, ValueError):
        raise SettingsError(
            "Workspace hook configuration needs review; it was not modified."
        ) from None


def ours(hook):
    # Match our exact module invocation, not arbitrary text mentioning the name.
    command = hook.get("command", "")
    try:
        parts = shlex.split(command)
        return any(parts[i : i + 2] == ["-m", MODULE] for i in range(len(parts) - 1))
    except (ValueError, AttributeError):
        return False


def integration(workspace, project, env_file, action="status"):
    root = workspace_path(workspace)
    data, path = hook_state(root)
    groups = data.get("hooks", {}).get("UserPromptSubmit", [])
    if not isinstance(groups, list) or any(
        not isinstance(g, dict) or not isinstance(g.get("hooks", []), list) for g in groups
    ):
        raise SettingsError("Workspace hooks need review; nothing was changed.")
    enabled = any(
        ours(h) for group in groups for h in group.get("hooks", []) if isinstance(h, dict)
    )
    command = [
        sys.executable,
        "-m",
        MODULE,
        "--env-file",
        str(env_file),
        "--workspace",
        str(root),
        "--project-id",
        project,
        "--enabled",
    ]
    hook = {
        "type": "command",
        "command": shlex.join(command),
        "commandWindows": subprocess.list2cmdline(command),
        "timeout": 5,
        "statusMessage": "Sending this user message to ContextBridge",
    }
    if action not in ("status", "preview", "install", "pause", "remove"):
        raise SettingsError("Unsupported capture action.")
    if action in ("install", "pause", "remove"):
        for group in groups:
            group["hooks"] = [
                h for h in group.get("hooks", []) if not (isinstance(h, dict) and ours(h))
            ]
        if action == "install":
            groups.append({"hooks": [hook]})
        data.setdefault("hooks", {})["UserPromptSubmit"] = groups
        path.parent.mkdir(mode=0o700, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        enabled = action == "install"
    return {
        "installed": enabled,
        "workspace": str(root),
        "hook": hook if action == "preview" else None,
        "notice": "Only future user messages are captured. Review /hooks in a fresh Codex session.",
    }
