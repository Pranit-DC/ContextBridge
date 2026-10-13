"""Opt-in Codex user-prompt capture through the existing authenticated ingestion API.

No transcript scraping, assistant/tool authority guessing, or local content queue. Empty receipt
files retain only event identity/time so retrying the same turn cannot reinterpret its timestamp.
"""

import argparse
import json
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from contextbridge.capture_adapters.transcript import TranscriptClient, unique_fields
from contextbridge.engine.errors import ModuleError
from contextbridge.mcp_adapter.config import MCPSettings

MAX_HOOK_BYTES = 64_000


def submit_prompt(payload, settings, workspace, *, client=None):
    root = Path(workspace).resolve(strict=True)
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "UserPromptSubmit":
        raise ModuleError("INVALID_INPUT")
    cwd = Path(payload.get("cwd", "")).resolve(strict=True)
    if not payload.get("cwd") or not cwd.is_relative_to(root):
        raise ModuleError("OUT_OF_SCOPE")
    prompt, session, turn = (payload.get(key) for key in ("prompt", "session_id", "turn_id"))
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 8000:
        raise ModuleError("INVALID_INPUT")
    if any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in (session, turn)):
        raise ModuleError("INVALID_INPUT")
    # Include the service binding: another project/service must not share replay identity.
    event_id = uuid5(
        NAMESPACE_URL, json.dumps([str(settings.api_url), settings.project_id, session, turn])
    )
    receipts = root / ".contextbridge" / "capture-receipts"
    if not receipts.resolve().is_relative_to(root):
        raise ModuleError("OUT_OF_SCOPE")
    receipts.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt = receipts / event_id.hex
    try:
        descriptor = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(descriptor)
    metadata = receipt.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ModuleError("INVALID_INPUT")
    event = {
        "schema_version": 1,
        "event_id": str(event_id),
        "scope": "project",
        "project_id": settings.project_id,
        "agent": "codex-user-prompt",
        "session": session,
        "interaction": turn,
        "occurred_at": datetime.fromtimestamp(metadata.st_mtime, UTC).isoformat(),
        # Standard authenticated import; no assertion that the server attests the host.
        "capture_method": "manual_import",
        "messages": [{"message_id": "user-prompt", "role": "user", "content": prompt}],
    }
    return (client or TranscriptClient(settings)).submit(event)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument(
        "--enabled",
        action="store_true",
        help="Explicitly enable sending user prompts to the configured memory service.",
    )
    args = parser.parse_args()
    if not args.enabled:
        return 0
    try:
        if not args.env_file.is_absolute() or not args.env_file.is_file():
            raise ModuleError("INVALID_INPUT")
        raw = sys.stdin.buffer.read(MAX_HOOK_BYTES + 1)
        if len(raw) > MAX_HOOK_BYTES:
            raise ModuleError("INVALID_INPUT")
        payload = json.loads(raw, object_pairs_hook=unique_fields)
        settings = MCPSettings(
            _env_file=args.env_file,
            project_id=args.project_id,
            agent_id="codex-user-prompt",
            request_timeout=3,
        )
        result = submit_prompt(payload, settings, args.workspace)
        message = (
            f"ContextBridge: queued for AI processing (job {result.job_id}). "
            "This is not confirmation that a memory was saved."
        )
    except Exception:
        # Do not interrupt Codex, expose prompt/configuration data, or falsely report capture.
        message = (
            "ContextBridge did not capture this message. Check the connection/project, "
            "input length and credentials; use the viewer to retry explicitly."
        )
    print(json.dumps({"continue": True, "systemMessage": message}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
