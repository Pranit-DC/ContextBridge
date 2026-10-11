"""Check user configuration locally, or explicitly request proposal-only model execution."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.extractor import invalid_constant, unique_object
from contextbridge.formation.providers.chat import (
    ChatClient,
    ChatEvidenceVerifier,
    ChatModelProvider,
)
from contextbridge.formation.providers.config import load_settings
from contextbridge.formation.validation import screened_event

MAX_EVENT_BYTES = 256_000


def read_event(path: Path) -> dict:
    with path.open("rb") as source:
        raw = source.read(MAX_EVENT_BYTES + 1)
    if len(raw) > MAX_EVENT_BYTES:
        raise ModuleError("INVALID_INPUT")
    payload = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    return screened_event(payload).model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--event", type=Path, help="Explicitly bound CapturedEvent JSON")
    parser.add_argument(
        "--execute", action="store_true", help="Opt in to model calls; never saves memory"
    )
    args = parser.parse_args()
    try:
        settings = load_settings(args.env_file)
        if not args.execute:
            print(
                json.dumps(
                    {
                        "mode": "configuration_check",
                        "network_called": False,
                        **settings.public_configuration(),
                    },
                    indent=2,
                )
            )
            return 0
        if args.event is None:
            raise ModuleError("INVALID_INPUT")
        settings.check_execution()
        event = read_event(args.event)
        verifier = ChatEvidenceVerifier(ChatClient(settings))
        extractor = Extractor(ChatModelProvider(ChatClient(settings)), verifier)
        candidates = extractor.extract(event)
        context = {"schema_version": 1, "checked_at": datetime.now(UTC).isoformat(), "records": []}
        admission = AdmissionPolicy(
            verifier, lambda event_id: event if event_id == event["event_id"] else None
        )
        decisions = [admission.assess(candidate, context) for candidate in candidates]
        print(
            json.dumps(
                {
                    "mode": "model_proposals",
                    "memory_saved": False,
                    "comparison": "empty_snapshot_not_production",
                    "quality_gate": "pending",
                    "candidates": candidates,
                    "decisions": decisions,
                },
                indent=2,
            )
        )
        return 0
    except ModuleError as exc:
        print(json.dumps({"code": exc.code, "retryable": exc.retryable}))
    except (OSError, ValueError, RecursionError):
        print(json.dumps({"code": "INVALID_INPUT", "retryable": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
