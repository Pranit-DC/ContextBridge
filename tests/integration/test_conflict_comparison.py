"""Real write transactions with injected admission/meaning proposals, not model quality tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.contracts import CapturedEvent
from contextbridge.engine.resolution import SafeResolutionPolicy
from contextbridge.engine.write import WriteEngine
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


class Comparisons:
    def __init__(self, relations):
        self.relations = relations
        self.seen = []

    def compare(self, candidate, record):
        content = record["memory"]["version"]["content"]
        self.seen.append(content)
        return self.relations[content]


def resolver(harness, relations):
    interpreter = Comparisons(relations)
    harness.modules = replace(harness.modules, resolution=SafeResolutionPolicy(interpreter))
    return interpreter


def save(harness, content, *, type_="DECISION", **changes):
    job, candidate, event = harness.enqueue(content, **changes)
    candidate["type"] = type_
    harness.extractor.outputs[event["event_id"]] = [candidate]
    result = harness.process(job)
    assert result.status == "succeeded"
    return result.memory_ids[0]


def snapshot(database):
    with Session(database[1]) as session:
        return [
            (m.id, m.type, m.current_version, v.id, v.content, v.decision_state, v.valid_to)
            for m, v in session.execute(
                select(Memory, MemoryVersion)
                .join(MemoryVersion)
                .order_by(Memory.id, MemoryVersion.number)
            )
        ], list(session.scalars(select(MemoryEdge.id)))


@pytest.mark.parametrize("type_", ["FACT", "STATE", "EVENT"])
@pytest.mark.parametrize("relation", ["same", "correction", "contradiction", "uncertain"])
def test_different_classification_is_compared_and_defers_without_mutation(
    database, type_, relation
):
    harness = Harness(database, formation_enabled=True)
    original = "The project uses PostgreSQL."
    save(harness, original, type_=type_)
    before = snapshot(database)
    interpreter = resolver(harness, {original: relation})
    result = harness.process(harness.enqueue("Use SQLite instead.")[0])
    assert interpreter.seen == [original]
    assert result.status == "deferred" and result.memory_ids == []
    assert result.reason_codes == ["INSUFFICIENT_EVIDENCE"]
    assert snapshot(database) == before


def test_unrelated_different_classification_can_coexist(database):
    harness = Harness(database, formation_enabled=True)
    original = "The migration finished."
    save(harness, original, type_="EVENT")
    interpreter = resolver(harness, {original: "unrelated"})
    save(harness, "Use PostgreSQL.")
    assert interpreter.seen == [original]
    assert len(snapshot(database)[0]) == 2


@pytest.mark.parametrize(
    "old_key,new_key", [(None, "database.primary"), ("db.primary", "storage.main")]
)
def test_semantic_comparison_handles_key_drift_and_preserves_versioned_evidence(
    database, old_key, new_key
):
    harness = Harness(database, formation_enabled=True)
    start = datetime.now(UTC) - timedelta(days=3)
    original = "Use PostgreSQL."
    memory_id = save(harness, original, claim_key=old_key, time=start)
    interpreter = resolver(harness, {original: "correction"})
    result = harness.process(
        harness.enqueue(
            "Use SQLite instead.",
            claim_key=new_key,
            time=start + timedelta(days=1),
            evidence="We replace PostgreSQL with SQLite; use SQLite instead.",
        )[0]
    )
    assert result.status == "succeeded" and result.memory_ids == [memory_id]
    assert interpreter.seen == [original]
    with harness.client() as client:
        detail = client.get(f"/v1/memories/{memory_id}").json()
    assert [v["content"] for v in detail["history"]] == [original, "Use SQLite instead."]
    assert detail["history"][0]["source"]["evidence"] == original
    assert detail["history"][0]["valid_to"] == detail["history"][1]["valid_from"]
    assert [edge["relation"] for edge in detail["edges"]] == ["supersedes"]


@pytest.mark.parametrize("relation", ["correction", "contradiction"])
def test_missing_candidate_key_does_not_authorize_mutation(database, relation):
    harness = Harness(database, formation_enabled=True)
    original = "Use PostgreSQL."
    save(harness, original)
    before = snapshot(database)
    interpreter = resolver(harness, {original: relation})
    result = harness.process(harness.enqueue("Use SQLite instead.", claim_key=None)[0])
    assert interpreter.seen == [original]
    assert result.status == "deferred" and snapshot(database) == before


@pytest.mark.parametrize(
    "content,relation,status,reason",
    [
        ("PostgreSQL is our selected relational store.", "same", "succeeded", "DUPLICATE"),
        ("Do not use PostgreSQL.", "contradiction", "succeeded", "INSUFFICIENT_EVIDENCE"),
        (
            "PostgreSQL might be the selected store.",
            "uncertain",
            "deferred",
            "INSUFFICIENT_EVIDENCE",
        ),
    ],
)
def test_paraphrase_negation_and_uncertainty_use_meaning_proposals(
    database, content, relation, status, reason
):
    harness = Harness(database, formation_enabled=True)
    original = "Use PostgreSQL."
    memory_id = save(harness, original)
    interpreter = resolver(harness, {original: relation})
    result = harness.process(harness.enqueue(content)[0])
    assert interpreter.seen == [original]
    assert result.status == status and result.reason_codes == [reason]
    rows, edges = snapshot(database)
    if relation == "contradiction":
        assert len(rows) == 2 and len(edges) == 1
        assert {row[5] for row in rows} == {"contested"}
    else:
        assert len(rows) == 1 and edges == [] and rows[0][5] == "clear"
        assert result.memory_ids == ([memory_id] if relation == "same" else [])


def test_multiple_conflicts_defer_instead_of_linking_only_the_first(database):
    harness = Harness(database, formation_enabled=True)
    first, second = "Use PostgreSQL.", "Use MySQL."
    save(harness, first)
    resolver(harness, {first: "unrelated"})
    save(harness, second)
    before = snapshot(database)
    interpreter = resolver(harness, {first: "contradiction", second: "contradiction"})
    result = harness.process(harness.enqueue("Use SQLite.")[0])
    assert set(interpreter.seen) == {first, second}
    assert result.status == "deferred" and result.memory_ids == []
    assert snapshot(database) == before


@pytest.mark.parametrize("relation", ["correction", "contradiction"])
def test_new_comparison_record_after_planning_prevents_partial_mutation(database, relation):
    harness = Harness(database, formation_enabled=True)
    original = "Use PostgreSQL."
    save(harness, original, time=datetime.now(UTC) - timedelta(days=3))
    resolver(harness, {original: relation})
    job, candidate, event = harness.enqueue("Use SQLite.")
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        engine.save_extraction(
            UUID(job), harness.modules.extract(CapturedEvent.model_validate(event))
        )
        engine.prepare(UUID(job), UUID(candidate["candidate_id"]))
    resolver(harness, {original: "unrelated"})
    save(harness, "Use MySQL.", type_="FACT")
    before = snapshot(database)
    result = harness.process(job)
    assert result.status == "deferred" and result.reason_codes == ["VERSION_CONFLICT"]
    assert snapshot(database) == before


def test_comparison_context_never_crosses_owner_project_or_conditions(database):
    harness = Harness(database, formation_enabled=True)
    save(Harness(database, owner="other-owner"), "Other owner's PostgreSQL.")
    save(Harness(database, project="other-project"), "Other project's PostgreSQL.")
    save(harness, "Use PostgreSQL in production.", conditions={"environment": "production"})
    interpreter = resolver(harness, {})  # Any unauthorized comparison fails this job.
    save(harness, "Use SQLite in staging.", conditions={"environment": "staging"})
    assert interpreter.seen == []
