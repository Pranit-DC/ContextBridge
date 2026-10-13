"""Generate or install a project-scoped opt-in Codex user-prompt hook."""

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--env-file", type=Path, default=Path(__file__).resolve().parents[1] / ".env.mcp"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Enable workspace capture; Codex still requires its normal hook trust review.",
    )
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    if not args.project_id.strip() or len(args.project_id) > 128 or not args.env_file.is_file():
        parser.error(
            "Provide an existing workspace, private adapter env file and valid project ID."
        )
    command = [
        sys.executable,
        "-m",
        "contextbridge.capture_adapters.codex_hook",
        "--env-file",
        str(args.env_file.resolve()),
        "--workspace",
        str(root),
        "--project-id",
        args.project_id,
        "--enabled",
    ]
    hook = {
        "type": "command",
        "command": shlex.join(command),
        "commandWindows": subprocess.list2cmdline(command),
        "timeout": 5,
        "statusMessage": "Sending this user message to ContextBridge",
    }
    directory = root / (".codex" if args.install else ".contextbridge")
    directory.mkdir(exist_ok=True)
    target = directory / ("hooks.json" if args.install else "codex-hooks.json")
    data = json.loads(target.read_text()) if target.exists() else {}
    hooks = data.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
    # Replace only our hook, preserving every other installed hook/event.
    for entry in hooks:
        entry["hooks"] = [
            h
            for h in entry.get("hooks", [])
            if "contextbridge.capture_adapters.codex_hook" not in h.get("command", "")
        ]
    hooks.append({"hooks": [hook]})
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(temporary, target)
    print(f"{'Installed' if args.install else 'Generated'} {target}")
    print(
        "Capture sends future user messages from this workspace to the configured memory service "
        "and online AI provider. It does not scan old chats or capture assistant/tool messages."
    )
    print(
        "Review the hook with /hooks in a fresh Codex session before use. "
        "The memory service capture project must match."
    )


if __name__ == "__main__":
    main()
