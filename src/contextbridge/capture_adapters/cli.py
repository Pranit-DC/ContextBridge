"""Native Linux/Windows transcript import through the same authenticated API."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from contextbridge.capture_adapters.transcript import TranscriptClient
from contextbridge.engine.errors import ModuleError
from contextbridge.mcp_adapter.config import MCPSettings


def main():
    parser = argparse.ArgumentParser(description="Explicit ContextBridge transcript import")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--api-url")
    parser.add_argument("--allow-developer", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "submit", "validate-bundle", "submit-bundle"):
        commands.add_parser(name).add_argument("file", type=Path)
    commands.add_parser("status").add_argument("job_id")
    args = parser.parse_args()
    if args.env_file and (not args.env_file.is_absolute() or not args.env_file.is_file()):
        print("Explicit env-file must be an existing absolute path.", file=sys.stderr)
        return 2
    try:
        settings = MCPSettings(
            _env_file=args.env_file,
            project_id=args.project_id,
            **({"api_url": args.api_url} if args.api_url else {}),
        )
        client = TranscriptClient(settings, allow_developer=args.allow_developer)
        if args.command.endswith("-bundle"):
            from contextbridge.evidence_time.client import BundleClient

            client = BundleClient(settings, allow_developer=args.allow_developer)
        if args.command == "status":
            result = client.status(args.job_id).model_dump(mode="json")
        else:
            event = client.read(args.file)
            if args.command == "validate-bundle":
                result = {
                    "bundle_id": str(event.bundle_id),
                    "project_id": event.events[0].project_id,
                    "event_count": len(event.events),
                    "status": "valid",
                }
            elif args.command == "validate":
                result = {
                    "event_id": str(event.event_id),
                    "project_id": event.project_id,
                    "message_count": len(event.messages),
                    "status": "valid",
                }
            else:
                result = client.submit(event.model_dump(mode="json")).model_dump(mode="json")
        print(json.dumps(result))
        return 0
    except (ValidationError, OSError):
        print("Invalid importer configuration.", file=sys.stderr)
        return 2
    except ModuleError as error:
        print(json.dumps({"code": error.code, "retryable": error.retryable}), file=sys.stderr)
        if args.command.startswith("submit"):
            print(
                "No automatic retry. A lost response may have accepted the event; reuse its "
                "original IDs and identical payload. Never replay cancelled or forgotten input.",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
