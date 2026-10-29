"""Phase 4 extraction protocol/engine checks, using synthetic hosted HTTP responses."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.models import CaptureCandidate, Memory, MemoryVersion
from tests.formation.test_grounded_provider import wire
from tests.integration.phase4_fakes import HostedReplay, extraction_response
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def test_atomic_claims_preserve_negation_conditions_rare_detail_and_raw_metadata(
    database, monkeypatch, tmp_path
):
    harness = Harness(database)
    now = datetime.now(UTC) - timedelta(minutes=1)
    statements = [
        (
            "FACT",
            "contextbridge uses PostgreSQL only in production.",
            {"environment": "production"},
        ),
        ("FACT", "contextbridge must not cache failed payments.", {}),
        ("LESSON", "After error E731, run repair_index.py with --dry-run first.", {}),
        ("PREFERENCE", "I prefer explicit type annotations.", {}),
        ("STATE", "contextbridge release is frozen.", {}),
        ("EVENT", "contextbridge backup completed at 2026-10-01T12:30:00Z.", {}),
    ]
    text = "\n".join(s[1] for s in statements)
    _, base, event = harness.enqueue(text, time=now)
    event["event_id"] = str(uuid4())
    event["messages"] = [
        {"message_id": f"claim-{i}", "role": "user", "content": statement[1]}
        for i, statement in enumerate(statements)
    ]
    with harness.client() as api:
        accepted = api.post("/v1/interactions", json=event)
        assert accepted.status_code == 202
        job = accepted.json()["job_id"]
    candidates = []
    for i, (kind, content, conditions) in enumerate(statements):
        candidate = deepcopy(base)
        candidate.update(
            candidate_id=str(uuid4()),
            event_id=event["event_id"],
            type=kind,
            content=content,
            conditions=conditions,
            claim_key=None,
        )
        candidate["source"]["evidence"] = content
        candidate["evidence_refs"] = [{"event_id": event["event_id"], "message_id": f"claim-{i}"}]
        candidates.append(candidate)
    raw = deepcopy(candidates)
    # The source-backed occurrence correction must stay distinguishable from raw output.
    raw[-1]["type"] = "FACT"
    candidates[-1]["valid_from"] = "2026-10-01T12:30:00+00:00"

    def respond(name, payload):
        return extraction_response(raw if name == "Claims" else candidates, name, payload)

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    produced = replay.providers.modules.extractor.extract(event)
    assert [c["content"] for c in produced] == [c["content"] for c in candidates]
    assert [c["type"] for c in produced] == [s[0] for s in statements]
    assert produced[0]["conditions"] == {"environment": "production"}
    assert datetime.fromisoformat(produced[-1]["valid_from"]) == datetime.fromisoformat(
        candidates[-1]["valid_from"]
    )
    assert raw[-1]["type"] == "FACT" and raw[-1]["valid_from"] == event["occurred_at"]
    provider = replay.backends.extraction_provider
    assert provider.type_corrections == provider.time_corrections == 1
    (tmp_path / "extraction-stages.json").write_text(
        json.dumps(
            {
                "mode": "synthetic_http_replay",
                "model_quality_measured": False,
                "raw_provider_claims": [wire(c) for c in raw],
                "local_corrections": {
                    "type": provider.type_corrections,
                    "time": provider.time_corrections,
                },
                "final_candidates": produced,
                "mock_request_count": len(replay.requests),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Persist through the actual engine without conflating relation-model quality with extraction.
    harness.extractor.outputs[event["event_id"]] = produced
    harness.set_relation("unrelated")
    result = harness.process(job)
    assert result.status == "succeeded" and len(result.memory_ids) == len(statements)
    with Session(database[1]) as db:
        rows = list(db.scalars(select(CaptureCandidate)))
        assert len(rows) == len(statements)
        assert len(list(db.scalars(select(Memory)))) == len(statements)
        assert {v.content for v in db.scalars(select(MemoryVersion))} == set(
            s[1] for s in statements
        )
    assert replay.snapshot() == {"calls": {"groq": 2, "cloudflare": 0}, "stopped": False}


@pytest.mark.parametrize("scope", ["developer", "project"])
def test_uncertain_evidence_never_commits_a_claim(database, monkeypatch, tmp_path, scope):
    harness = Harness(database, capture_allow_developer=True)
    job, candidate, event = harness.enqueue("contextbridge may use SQLite; this is undecided.")

    # Project binding is not a proof of semantic support. This audited uncertainty must defer.
    def respond(name, payload):
        result = extraction_response([candidate], name, payload)
        if name == "Checks":
            result["checks"][0]["support"] = "uncertain"
        return result

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    if scope == "developer":
        candidate.update(scope="developer", project_id=None)
        event.update(scope="developer", project_id=None)
        produced = replay.providers.modules.extractor.extract(event)
        context = {"schema_version": 1, "checked_at": datetime.now(UTC).isoformat(), "records": []}
        # Supply the same synthetic event to the standalone admission lookup.
        replay.providers.modules.admission.event_lookup = lambda _: event
        assert replay.providers.modules.admission.assess(produced[0], context)["outcome"] == "DEFER"
    else:
        result = harness.process(job, replay.providers.modules)
        assert result.status == "deferred" and not result.memory_ids
    with Session(database[1]) as db:
        assert db.scalar(select(Memory)) is None
