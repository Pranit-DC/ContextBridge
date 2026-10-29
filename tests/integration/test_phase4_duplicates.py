"""Fresh event IDs reproduce the prior repeated-statement failure offline."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.models import Memory, MemoryVersion
from tests.integration.phase4_fakes import HostedReplay, extraction_response
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "variation",
    ["exact", "paraphrase", "category", "condition", "evidenced_condition", "unrelated_category"],
)
def test_repeated_claim_does_not_create_another_current_truth(
    database, monkeypatch, tmp_path, variation
):
    harness = Harness(database)
    # Match the earlier online statement's wording, including its missing "the".
    text = "Use PostgreSQL as primary database for contextbridge."
    first, old, _ = harness.enqueue(text, time=datetime.now(UTC) - timedelta(minutes=2))
    candidates = [old]

    def respond(name, payload):
        if name in {"Claims", "Checks"}:
            return extraction_response(candidates, name, payload)
        if name == "DuplicateResponse":
            return {"relation": "equivalent"}
        if name == "RelationResponse":
            return {"relation": "same", "correction_evidence": None}
        raise AssertionError(name)

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    original = harness.process(first, replay.providers.modules)
    assert original.status == "succeeded" and len(original.memory_ids) == 1
    second_text = (
        text
        if variation in {"exact", "condition", "evidenced_condition"}
        else ("PostgreSQL is the primary store for contextbridge.")
    )
    if variation == "unrelated_category":
        second_text = "contextbridge runs on Python 3.12."
    second, new, event = harness.enqueue(
        second_text,
        time=datetime.now(UTC) - timedelta(minutes=1),
        evidence=("In production, " + second_text) if variation == "evidenced_condition" else None,
        conditions={"environment": "production"} if "condition" in variation else {},
    )
    if variation == "category":
        new["type"] = "FACT"
    elif variation == "unrelated_category":
        new.update(type="FACT", claim_key="project.runtime.python")
    candidates[:] = [new]
    result = harness.process(second, replay.providers.modules)
    if variation in {"category", "condition"}:
        assert result.status == "deferred" and not result.memory_ids
    elif variation in {"evidenced_condition", "unrelated_category"}:
        assert result.status == "succeeded" and result.memory_ids != original.memory_ids
    else:
        assert result.status == "succeeded" and result.reason_codes == ["DUPLICATE"]
    before = len(replay.requests)
    harness.process(second, replay.providers.modules)
    assert len(replay.requests) == before  # durable replay, not another extraction
    with Session(database[1]) as db:
        expected = 2 if variation in {"evidenced_condition", "unrelated_category"} else 1
        assert db.scalar(select(func.count()).select_from(Memory)) == expected
        assert db.scalar(select(func.count()).select_from(MemoryVersion)) == expected
    assert event["event_id"] != old["event_id"]
    assert replay.snapshot()["calls"]["groq"] == before <= 5
