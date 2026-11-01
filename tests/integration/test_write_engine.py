from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.contracts import CapturedEvent
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.write import WriteEngine
from contextbridge.models import (
    CaptureCandidate,
    CaptureEvent,
    Memory,
    MemoryEdge,
    MemoryVersion,
)
from contextbridge.persistence.relationships import add_derivation
from contextbridge.schemas import CreateMemory
from contextbridge.service import MemoryService
from tests.integration.write_fakes import Admit, Harness

pytestmark = pytest.mark.integration


def count(database, model):
    with Session(database[1]) as session:
        return session.scalar(select(func.count()).select_from(model))


def test_new_claim_and_restart_replay_are_one_mutation(database):
    harness = Harness(database)
    job_id, candidate, _ = harness.enqueue()
    first = harness.process(job_id)
    assert first.status == "succeeded" and len(first.memory_ids) == 1
    second = harness.process(job_id)
    assert second.memory_ids == first.memory_ids
    assert len(harness.extractor.calls) == 1
    assert count(database, Memory) == count(database, MemoryVersion) == 1
    with Session(database[1]) as session:
        memory, version = session.execute(select(Memory, MemoryVersion).join(MemoryVersion)).one()
        assert memory.claim_key == candidate["claim_key"]
        assert version.confidence == candidate["confidence"]
        assert version.evidence == candidate["source"]["evidence"]


def test_exact_duplicate_and_different_conditions_do_not_overwrite(database):
    harness = Harness(database)
    first = harness.process(harness.enqueue()[0])
    duplicate = harness.process(harness.enqueue()[0])
    conditional = harness.process(
        harness.enqueue("Use SQLite.", conditions={"environment": "test"})[0]
    )
    assert duplicate.memory_ids == first.memory_ids
    assert conditional.memory_ids != first.memory_ids
    assert count(database, Memory) == count(database, MemoryVersion) == 2
    assert count(database, MemoryEdge) == 0


def test_candidate_duplicate_reuses_legacy_explicit_memory(database):
    harness = Harness(database)
    job_id, candidate, _ = harness.enqueue()
    with Session(database[1], expire_on_commit=False) as session:
        explicit = MemoryService(session, harness.settings.developer_id).create(
            CreateMemory(
                request_id=uuid4(),
                scope=candidate["scope"],
                project_id=candidate["project_id"],
                type=candidate["type"],
                content=candidate["content"],
                conditions=candidate["conditions"],
                source=candidate["source"],
                valid_from=candidate["valid_from"],
            )
        )
    result = harness.process(job_id)
    assert result.status == "succeeded" and result.memory_ids == [explicit.id]
    assert result.reason_codes == ["DUPLICATE"]
    assert count(database, Memory) == count(database, MemoryVersion) == 1
    with Session(database[1]) as session:
        assert session.scalar(select(Memory.claim_key)) is None


def test_explicit_supported_correction_preserves_versions_and_edges(database):
    harness = Harness(database)
    first = harness.process(harness.enqueue()[0])
    harness.set_relation("correction")
    correction = harness.enqueue(
        "Use SQLite.",
        time=datetime.now(UTC) - timedelta(days=1),
        evidence="We explicitly replace the previous PostgreSQL decision: use SQLite.",
    )
    updated = harness.process(correction[0])
    assert updated.memory_ids == first.memory_ids
    assert count(database, Memory) == 1 and count(database, MemoryVersion) == 2
    with harness.client() as client:
        inspected = client.get(f"/v1/memories/{first.memory_ids[0]}").json()
    assert inspected["history"][0]["status"] == "SUPERSEDED"
    assert inspected["history"][1]["content"] == "Use SQLite."
    assert inspected["edges"][0]["relation"] == "supersedes"


def test_contradiction_remains_visible_as_contested(database):
    harness = Harness(database)
    first = harness.process(harness.enqueue()[0])
    harness.set_relation("contradiction")
    conflicting = harness.process(harness.enqueue("Use SQLite.")[0])
    assert conflicting.status == "succeeded" and conflicting.memory_ids != first.memory_ids
    with Session(database[1]) as session:
        assert set(session.scalars(select(MemoryVersion.decision_state))) == {"contested"}
        assert session.scalar(select(MemoryEdge.relation)) == "contradicts"
    with harness.client() as client:
        response = client.post(
            "/v1/inspection/browse",
            json={"schema_version": 1, "scope": "project", "project_id": "contextbridge"},
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2
        assert {item["decision_state"] for item in response.json()["items"]} == {"contested"}


@pytest.mark.parametrize("reason", ["uncertain", "backdated"])
def test_unsupported_or_backdated_correction_defers(database, reason):
    harness = Harness(database)
    harness.process(harness.enqueue()[0])
    if reason == "backdated":
        harness.set_relation("correction")
    job_id, _, _ = harness.enqueue("Use SQLite.", time=datetime.now(UTC) - timedelta(days=3))
    result = harness.process(job_id)
    assert result.status == "deferred" and result.memory_ids == []
    assert result.reason_codes == [
        "AMBIGUOUS_TIME" if reason == "backdated" else "INSUFFICIENT_EVIDENCE"
    ]
    assert count(database, MemoryVersion) == 1
    assert harness.process(job_id).status == "deferred"
    assert len(harness.extractor.calls) == 2


def test_rejected_candidate_keeps_no_content_copy(database):
    harness = Harness(database, admission=Admit("REJECT"))
    result = harness.process(harness.enqueue()[0])
    assert result.status == "succeeded" and result.memory_ids == []
    with Session(database[1]) as session:
        saved = session.scalar(select(CaptureCandidate))
        assert saved.status == "rejected" and saved.payload is None and saved.fingerprint is None
    assert count(database, Memory) == 0


def test_extraction_is_not_repeated_after_transient_admission_failure(database):
    class FlakyAdmission:
        def __init__(self):
            self.calls = 0

        def assess(self, candidate, context):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("private-provider-text")
            return Admit().assess(candidate, context)

    provider = FlakyAdmission()
    harness = Harness(database, admission=provider)
    job_id, _, _ = harness.enqueue()
    failed = harness.process(job_id)
    assert failed.status == "deferred" and failed.reason_codes == ["PROVIDER_UNAVAILABLE"]
    assert harness.process(job_id).status == "succeeded"
    assert len(harness.extractor.calls) == 1 and provider.calls == 2


def test_empty_extraction_and_malformed_output_have_different_status(database):
    harness = Harness(database)
    job_id, _, event = harness.enqueue()
    harness.extractor.outputs[event["event_id"]] = []
    assert harness.process(job_id).status == "succeeded"
    second, _, event = harness.enqueue()
    harness.extractor.outputs[event["event_id"]] = [{"private-field": "private-value"}]
    response = harness.process(second)
    assert response.status == "failed" and response.reason_codes == ["INVALID_PROVIDER_OUTPUT"]
    with Session(database[1]) as session:
        assert (
            session.scalar(
                select(CaptureEvent.extraction_complete).where(
                    CaptureEvent.event_id == UUID(event["event_id"])
                )
            )
            is False
        )


def test_candidate_identity_cannot_be_reused_in_another_event(database):
    harness = Harness(database)
    first, original, _ = harness.enqueue()
    harness.process(first)
    second, _, event = harness.enqueue("A different decision.")
    harness.extractor.outputs[event["event_id"]][0]["candidate_id"] = original["candidate_id"]
    result = harness.process(second)
    assert result.status == "failed" and count(database, Memory) == 1


def test_saved_plan_survives_restart_and_cannot_be_reinterpreted(database):
    harness = Harness(database)
    job_id, candidate, event = harness.enqueue()
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        engine.save_extraction(
            UUID(job_id), harness.modules.extract(CapturedEvent.model_validate(event))
        )
        engine.prepare(UUID(job_id), UUID(candidate["candidate_id"]))

    class ChangedResolver:
        def resolve(self, candidate, context):
            raise AssertionError("Cached plan must be reused")

    modules = ModuleGateway(
        extractor=harness.extractor, admission=Admit(), resolution=ChangedResolver()
    )
    assert harness.process(job_id, modules).status == "succeeded"
    assert len(harness.extractor.calls) == 1 and count(database, MemoryVersion) == 1


def test_correction_commit_failure_rolls_back_and_reuses_saved_plan(database):
    harness = Harness(database)
    original = harness.process(harness.enqueue()[0]).memory_ids[0]
    harness.set_relation("correction")
    job_id, candidate, event = harness.enqueue(
        "Use SQLite.", time=datetime.now(UTC) - timedelta(days=1)
    )
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        engine.save_extraction(
            UUID(job_id), harness.modules.extract(CapturedEvent.model_validate(event))
        )
        engine.prepare(UUID(job_id), UUID(candidate["candidate_id"]))

        def fail_commit(active_session):
            # Flush content, closed intervals, and edges before simulating lost storage.
            active_session.flush()
            raise SQLAlchemyError("private database diagnostic")

        sqlalchemy_event.listen(session, "before_commit", fail_commit, once=True)
        with pytest.raises(SQLAlchemyError):
            engine.execute(UUID(job_id), UUID(candidate["candidate_id"]))
        session.rollback()
    assert count(database, MemoryVersion) == 1 and count(database, MemoryEdge) == 0
    with Session(database[1]) as session:
        assert session.get(Memory, original).current_version == 1
        assert session.scalar(select(MemoryVersion.valid_to)) is None
        assert (
            session.scalar(
                select(CaptureCandidate.status).where(
                    CaptureCandidate.candidate_id == UUID(candidate["candidate_id"])
                )
            )
            == "pending"
        )
    retried = harness.process(job_id)
    assert retried.status == "succeeded" and retried.memory_ids == [original]
    assert count(database, MemoryVersion) == 2 and count(database, MemoryEdge) == 1
    assert len(harness.extractor.calls) == 2  # One original event and one saved correction.


def test_competing_corrections_cannot_both_commit(database):
    harness = Harness(database)
    harness.process(harness.enqueue()[0])
    harness.set_relation("correction")
    proposals = [
        harness.enqueue(content, time=datetime.now(UTC) - timedelta(days=1))
        for content in ["Use SQLite.", "Use MySQL."]
    ]
    for job_id, candidate, event in proposals:
        with Session(database[1], expire_on_commit=False) as session:
            engine = WriteEngine(session, harness.settings, harness.modules)
            engine.save_extraction(
                UUID(job_id), harness.modules.extract(CapturedEvent.model_validate(event))
            )
            engine.prepare(UUID(job_id), UUID(candidate["candidate_id"]))
    gate = Barrier(2)

    def execute(proposal):
        job_id, candidate, _ = proposal
        with Session(database[1], expire_on_commit=False) as session:
            engine = WriteEngine(session, harness.settings, harness.modules)
            gate.wait(timeout=10)
            engine.execute(UUID(job_id), UUID(candidate["candidate_id"]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(execute, proposals))
    outcomes = [harness.process(proposal[0]) for proposal in proposals]
    assert sorted(result.status for result in outcomes) == ["deferred", "succeeded"]
    assert count(database, Memory) == 1 and count(database, MemoryVersion) == 2
    assert any("VERSION_CONFLICT" in result.reason_codes for result in outcomes)


def test_concurrent_jobs_deduplicate_their_new_claim(database):
    harness = Harness(database)
    jobs = [harness.enqueue() for _ in range(2)]
    for job_id, candidate, event in jobs:
        with Session(database[1], expire_on_commit=False) as session:
            engine = WriteEngine(session, harness.settings, harness.modules)
            engine.save_extraction(
                UUID(job_id), harness.modules.extract(CapturedEvent.model_validate(event))
            )
            engine.prepare(UUID(job_id), UUID(candidate["candidate_id"]))
    gate = Barrier(2)

    def execute(proposal):
        job_id, candidate, _ = proposal
        with Session(database[1], expire_on_commit=False) as session:
            gate.wait(timeout=10)
            WriteEngine(session, harness.settings, harness.modules).execute(
                UUID(job_id), UUID(candidate["candidate_id"])
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(execute, jobs))
    assert count(database, Memory) == count(database, MemoryVersion) == 1


def test_forget_purges_capture_artifacts_and_blocks_redelivery(database):
    harness = Harness(database)
    job_id, _, _ = harness.enqueue()
    memory_id = harness.process(job_id).memory_ids[0]
    with harness.client() as client:
        assert client.delete(f"/v1/memories/{memory_id}").status_code == 204
    assert count(database, Memory) == count(database, MemoryVersion) == 0
    assert harness.process(job_id).status == "cancelled"
    with Session(database[1]) as session:
        saved = session.scalar(select(CaptureCandidate))
        event = session.scalar(select(CaptureEvent))
        assert saved.payload is saved.fingerprint is saved.plan is saved.admission is None
        assert event.payload is event.fingerprint is None


def test_forget_during_resolution_cannot_recreate_the_target(database):
    from contextbridge.engine.resolution import SafeResolutionPolicy
    from tests.integration.write_fakes import Relation

    harness = Harness(database)
    target = harness.process(harness.enqueue()[0]).memory_ids[0]
    job_id, _, _ = harness.enqueue("Use SQLite.", time=datetime.now(UTC) - timedelta(days=1))

    class ForgettingResolver:
        def resolve(self, candidate, context):
            with harness.client() as client:
                assert client.delete(f"/v1/memories/{target}").status_code == 204
            return SafeResolutionPolicy(Relation("correction")).resolve(candidate, context)

    modules = ModuleGateway(
        extractor=harness.extractor, admission=Admit(), resolution=ForgettingResolver()
    )
    assert harness.process(job_id, modules).status == "cancelled"
    assert count(database, Memory) == 0


def test_forget_after_prepare_cancels_the_cached_correction(database):
    harness = Harness(database)
    target = harness.process(harness.enqueue()[0]).memory_ids[0]
    harness.set_relation("correction")
    job_id, candidate, event = harness.enqueue(
        "Use SQLite.", time=datetime.now(UTC) - timedelta(days=1)
    )
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        engine.save_extraction(
            UUID(job_id), harness.modules.extract(CapturedEvent.model_validate(event))
        )
        engine.prepare(UUID(job_id), UUID(candidate["candidate_id"]))
    with harness.client() as client:
        client.delete(f"/v1/memories/{target}")
    assert harness.process(job_id).status == "cancelled"
    assert count(database, Memory) == 0


def test_candidate_expiry_invalidates_cached_objects_before_execute(database):
    harness = Harness(database)
    job_id, candidate, event = harness.enqueue()
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        engine.save_extraction(
            UUID(job_id), harness.modules.extract(CapturedEvent.model_validate(event))
        )
        engine.prepare(UUID(job_id), UUID(candidate["candidate_id"]))
        with database[1].begin() as connection:
            connection.execute(
                text("UPDATE capture_candidates SET expires_at = now() - interval '1 minute'")
            )
        with pytest.raises(ModuleError) as error:
            engine.execute(UUID(job_id), UUID(candidate["candidate_id"]))
        assert error.value.code == "CANCELLED"
    assert count(database, Memory) == 0


def test_engine_checks_owning_project_and_configured_owner(database):
    harness = Harness(database)
    job_id, _, _ = harness.enqueue()
    for outsider in [
        Harness(database, owner="other-owner"),
        Harness(database, project="other-project"),
    ]:
        with pytest.raises(EngineError) as error:
            outsider.process(job_id)
        assert error.value.code == "OUT_OF_SCOPE"
    assert count(database, Memory) == 0


def test_foreign_candidate_scope_and_assessment_ids_are_rejected(database):
    harness = Harness(database)
    job_id, _, event = harness.enqueue()
    harness.extractor.outputs[event["event_id"]][0]["project_id"] = "unrelated"
    assert harness.process(job_id).reason_codes == ["INVALID_PROVIDER_OUTPUT"]

    class WrongAdmission:
        def assess(self, candidate, context):
            return {**Admit().assess(candidate, context), "candidate_id": str(uuid4())}

    job_id, _, _ = harness.enqueue()
    assert harness.process(
        job_id, ModuleGateway(extractor=harness.extractor, admission=WrongAdmission())
    ).reason_codes == ["INVALID_PROVIDER_OUTPUT"]
    assert count(database, Memory) == 0


def test_derivation_is_scoped_and_forgetting_removes_transitive_summaries(database):
    harness = Harness(database)
    ids = [
        harness.process(harness.enqueue(content, claim_key=f"claim.{i}")[0]).memory_ids[0]
        for i, content in enumerate(["Source fact.", "Derived note.", "Derived summary."])
    ]
    with Session(database[1]) as session:
        versions = [
            session.scalar(select(MemoryVersion.id).where(MemoryVersion.memory_id == memory_id))
            for memory_id in ids
        ]
        add_derivation(session, harness.settings.developer_id, versions[1], versions[0])
        add_derivation(session, harness.settings.developer_id, versions[2], versions[1])
        session.commit()
    with harness.client() as client:
        assert client.delete(f"/v1/memories/{ids[0]}").status_code == 204
    assert (
        count(database, Memory)
        == count(database, MemoryVersion)
        == count(database, MemoryEdge)
        == 0
    )


def test_derivation_rejects_cross_project_edges(database):
    first = Harness(database)
    other = Harness(database, project="other-project")
    memories = [
        first.process(first.enqueue()[0]).memory_ids[0],
        other.process(other.enqueue()[0]).memory_ids[0],
    ]
    with Session(database[1]) as session:
        versions = [
            session.scalar(select(MemoryVersion.id).where(MemoryVersion.memory_id == memory_id))
            for memory_id in memories
        ]
        with pytest.raises(EngineError):
            add_derivation(session, first.settings.developer_id, *versions)
        session.rollback()
    assert count(database, MemoryEdge) == 0
