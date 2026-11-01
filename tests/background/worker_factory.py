"""Synthetic providers for subprocess/container probes only; never production configuration."""

import json
import os
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import WorkerProviders
from contextbridge.engine.modules import ModuleGateway
from contextbridge.formation import Extractor
from tests.engine.fakes import fixture


class RecordedExtractor:
    def extract(self, event):
        time.sleep(float(os.getenv("CONTEXTBRIDGE_PROBE_DELAY", "0")))
        candidate = fixture("candidate")
        message = next(m for m in event["messages"] if m["role"] == "user")
        candidate.update(
            candidate_id=str(uuid5(NAMESPACE_URL, event["event_id"])),
            event_id=event["event_id"],
            scope=event["scope"],
            project_id=event["project_id"],
            content=message["content"],
            valid_from=event["occurred_at"],
        )
        candidate["source"].update(
            kind="user",
            agent=event["agent"],
            session=event["session"],
            interaction=event["interaction"],
            evidence=message["content"],
        )
        candidate["evidence_refs"] = [
            {"event_id": event["event_id"], "message_id": message["message_id"]}
        ]
        return [candidate]


class RecordedAdmission:
    def assess(self, candidate, context):
        return {
            "schema_version": 1,
            "candidate_id": candidate["candidate_id"],
            "outcome": "ADMIT",
            "reason_codes": ["EXPLICIT_DECISION"],
        }


def make(settings, sessions):
    marker = os.getenv("CONTEXTBRIDGE_PROBE_CRASH_MARKER")
    if marker:
        original = WorkRunner.finish

        def crash_before_ack(self, *args, **kwargs):
            path = Path(marker)
            if not path.exists():
                path.write_text("committed", encoding="utf-8")
                os._exit(137)
            return original(self, *args, **kwargs)

        WorkRunner.finish = crash_before_ack

    class Backend:
        def generate(self, event):
            return json.dumps(RecordedExtractor().extract(event))

    class RecordedSupport:
        def verify(self, candidate, event):
            return "supported"  # Synthetic probe annotation, never semantic quality evidence.

    return WorkerProviders(
        ModuleGateway(
            extractor=Extractor(Backend(), RecordedSupport()), admission=RecordedAdmission()
        )
    )
