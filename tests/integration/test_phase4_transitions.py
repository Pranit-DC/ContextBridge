"""Current hosted relation proposals plus actual version/edge/retrieval transactions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.contracts import RetrievalQuery
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.service import MemoryService
from tests.integration.phase4_fakes import HostedReplay, extraction_response
from tests.integration.retrieval_fakes import create, query
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case", ["correction", "contradiction", "negated_correction", "conditions", "backdated"]
)
def test_relation_transitions_preserve_history_applicability_and_contested_context(
    database, monkeypatch, tmp_path, case
):
    harness = Harness(database)
    first, old, _ = harness.enqueue(
        "Use PostgreSQL database.", time=datetime.now(UTC) - timedelta(days=2)
    )
    candidates = [old]

    def respond(name, payload):
        if name in {"Claims", "Checks"}:
            return extraction_response(candidates, name, payload)
        if name == "DuplicateResponse":
            return {"relation": "different"}
        if name == "RelationResponse":
            return {
                "relation": "correction"
                if case in {"correction", "negated_correction", "backdated"}
                else "contradiction",
                "correction_evidence": candidates[0]["source"]["evidence"],
            }
        if name == "JudgmentResponse":
            return {"judgment": "supports"}
        raise AssertionError(name)

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    initial = harness.process(first, replay.providers.modules)
    historical = datetime.now(UTC) - timedelta(days=1)
    text = "Use SQLite database instead of PostgreSQL."
    if case == "negated_correction":
        text = "Do not switch the database to SQLite."
    elif case in {"contradiction", "conditions"}:
        text = "SQLite is our database."
    second, new, _ = harness.enqueue(
        text,
        time=datetime.now(UTC) - timedelta(days=3 if case == "backdated" else 0, minutes=1),
        conditions={"environment": "development"} if case == "conditions" else {},
    )
    candidates[:] = [new]
    result = harness.process(second, replay.providers.modules)
    with Session(database[1]) as db:
        inspection = MemoryService(db, "developer-a").inspect(initial.memory_ids[0])
        edges = list(db.scalars(select(MemoryEdge)))
        if case == "correction":
            assert result.memory_ids == initial.memory_ids
            assert [v.content for v in inspection.history] == [old["content"], text]
            assert inspection.history[0].valid_to == inspection.history[1].valid_from
            assert [(e.relation, e.from_version_id, e.to_version_id) for e in edges] == [
                ("supersedes", inspection.history[1].id, inspection.history[0].id)
            ]
        elif case == "contradiction":
            assert len(result.memory_ids) == 1 and result.memory_ids != initial.memory_ids
            assert [e.relation for e in edges] == ["contradicts"]
            assert set(db.scalars(select(MemoryVersion.decision_state))) == {"contested"}
        elif case == "conditions":
            assert result.status == "succeeded" and len(result.memory_ids) == 1
            assert edges == []
            assert set(db.scalars(select(MemoryVersion.decision_state))) == {"clear"}
        else:
            assert result.status == "deferred" and not result.memory_ids and edges == []
            assert len(inspection.history) == 1
        service = RetrievalService(
            db, harness.settings, replay.providers.modules, verifier=replay.providers.verifier
        )
        before = service.search(RetrievalQuery.model_validate(query(as_of=historical.isoformat())))
        assert [c.content for c in before.cards] == [old["content"]]
        current = service.search(RetrievalQuery.model_validate(query()))
        if case == "contradiction":
            assert len(current.cards) == 2
            assert {c.decision_state for c in current.cards} == {"contested"}
            assert {c.verification for c in current.cards} == {"uncertain"}
        if case == "correction":
            assert [c.content for c in current.cards] == [text]
    assert replay.snapshot()["calls"]["groq"] <= 9


def test_multiple_conflicts_defer_without_partially_marking_one_target(
    database, monkeypatch, tmp_path
):
    old = [create(database, "Use PostgreSQL database."), create(database, "Use MySQL database.")]
    harness = Harness(database)
    job, candidate, _ = harness.enqueue("Use SQLite database.", time=datetime.now(UTC))

    def respond(name, payload):
        if name in {"Claims", "Checks"}:
            return extraction_response([candidate], name, payload)
        if name == "DuplicateResponse":
            return {"relation": "different"}
        return {"relation": "contradiction", "correction_evidence": None}

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    result = harness.process(job, replay.providers.modules)
    assert result.status == "deferred" and not result.memory_ids
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == len(old)
        assert db.scalar(select(MemoryEdge)) is None
        assert set(db.scalars(select(MemoryVersion.decision_state))) == {"clear"}
    assert replay.snapshot()["calls"]["groq"] == 5


@pytest.mark.xfail(
    strict=True, reason="Om: hosted interpreter excludes cross-type keyless comparisons"
)
def test_keyless_cross_category_paraphrased_conflict_must_not_become_clear_truth(
    database, monkeypatch, tmp_path
):
    create(database, "Use PostgreSQL database.")
    harness = Harness(database)
    job, candidate, _ = harness.enqueue(
        "SQLite is our database.", claim_key=None, time=datetime.now(UTC)
    )
    candidate["type"] = "FACT"

    def respond(name, payload):
        if name == "RelationResponse":
            return {"relation": "contradiction", "correction_evidence": None}
        return extraction_response([candidate], name, payload)

    replay = HostedReplay(
        harness,
        monkeypatch,
        tmp_path,
        respond,
    )
    result = harness.process(job, replay.providers.modules)
    assert result.status == "deferred" and not result.memory_ids
