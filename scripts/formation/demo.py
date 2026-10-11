"""Run the synthetic contract fixtures without an agent, model account, or database."""

import argparse
import json
from pathlib import Path

from contextbridge.contracts import Candidate, CapturedEvent
from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor, import_transcript
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duplicate", action="store_true", help="Compare against the stored fixture"
    )
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parents[2] / "docs" / "team-plan" / "fixtures"
    try:
        event = CapturedEvent.model_validate(
            json.loads((fixtures / "captured-event.json").read_text(encoding="utf-8"))
        ).model_dump(mode="json")
        candidate = Candidate.model_validate(
            json.loads((fixtures / "candidate.json").read_text(encoding="utf-8"))
        ).model_dump(mode="json")
        imported = import_transcript(
            event["messages"],
            **{
                key: event[key]
                for key in (
                    "event_id",
                    "scope",
                    "project_id",
                    "agent",
                    "session",
                    "interaction",
                    "occurred_at",
                )
            },
        )
        verifier = RecordedEvidenceVerifier([(event, candidate, "supported")])
        proposals = Extractor(RecordedProvider(event, json.dumps([candidate])), verifier).extract(
            imported
        )
        records = []
        if args.duplicate:
            records = json.loads(
                (fixtures / "retrieval-snapshot.json").read_text(encoding="utf-8")
            )["records"]
        context = {"schema_version": 1, "checked_at": "2026-10-09T11:00:00Z", "records": records}
        admission = AdmissionPolicy(
            verifier, lambda event_id: event if event_id == event["event_id"] else None
        )
        print(
            json.dumps(
                {
                    "mode": "recorded_fixture",
                    "model_quality_measured": False,
                    "candidates": proposals,
                    "decisions": [admission.assess(proposal, context) for proposal in proposals],
                },
                indent=2,
            )
        )
    except ModuleError as exc:
        print(json.dumps({"code": exc.code, "retryable": exc.retryable}))
        return 1
    except (OSError, ValueError):
        print(json.dumps({"code": "INVALID_INPUT", "retryable": False}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
