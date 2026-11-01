"""Real PostgreSQL/engine integration with explicitly recorded formation providers."""

import json
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import CapturedEvent
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.resolution import SafeResolutionPolicy
from contextbridge.engine.write import WriteEngine
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider
from contextbridge.models import CaptureCandidate, CaptureEvent, Memory, MemoryEdge, MemoryVersion
from contextbridge.service import MemoryService
from scripts.formation.check_admission import load_examples
from tests.conftest import TEST_TOKEN

pytestmark = pytest.mark.integration


def setup(database, event, candidate, *, admission_support="supported", resolution=None):
    settings = Settings(
        _env_file=None,
        database_url=database[0],
        api_token=TEST_TOKEN,
        developer_id="formation-test-developer",
        capture_project_id=event["project_id"],
    )
    extraction_verifier = RecordedEvidenceVerifier([(event, candidate, "supported")])
    admission_verifier = RecordedEvidenceVerifier([(event, candidate, admission_support)])
    modules = ModuleGateway(
        extractor=Extractor(RecordedProvider(event, json.dumps([candidate])), extraction_verifier),
        admission=AdmissionPolicy(
            admission_verifier,
            lambda event_id: event if event_id == event["event_id"] else None,
        ),
        resolution=resolution,
    )
    with Session(database[1], expire_on_commit=False) as session:
        job = IngestionService(session, settings).ingest(CapturedEvent.model_validate(event))
    return settings, modules, UUID(str(job.job_id))


def test_formation_engine_replay_and_forget(database, event, candidate):
    settings, modules, job_id = setup(database, event, candidate)
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, settings, modules)
        first = engine.process(job_id)
        assert first.status == "succeeded" and len(first.memory_ids) == 1
        assert engine.process(job_id).memory_ids == first.memory_ids
        assert session.scalar(select(func.count()).select_from(Memory)) == 1
        assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 1
        inspected = MemoryService(session, settings.developer_id).inspect(first.memory_ids[0])
        assert inspected.memory.version.content == candidate["content"]
        assert inspected.memory.version.source.evidence == candidate["source"]["evidence"]
        MemoryService(session, settings.developer_id).forget(first.memory_ids[0])
        assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 0
        assert session.scalar(select(CaptureEvent.payload)) is None
        assert session.scalar(select(CaptureCandidate.payload)) is None
        assert engine.ingestion.inspect_job(job_id).status == "cancelled"


@pytest.mark.parametrize(
    "support,status", [("unsupported", "succeeded"), ("uncertain", "deferred")]
)
def test_admission_cannot_write_rejected_or_deferred_claims(
    database, event, candidate, support, status
):
    settings, modules, job_id = setup(database, event, candidate, admission_support=support)
    with Session(database[1], expire_on_commit=False) as session:
        result = WriteEngine(session, settings, modules).process(job_id)
        assert result.status == status
        assert result.memory_ids == []
        assert session.scalar(select(func.count()).select_from(Memory)) == 0


def new_delivery(example):
    """Bind stable IDs to this separate synthetic delivery without changing its evidence."""
    event, candidate = example["event"], example["candidate"]
    event["event_id"] = str(uuid5(NAMESPACE_URL, f"formation:o2:event:{example['id']}"))
    candidate["event_id"] = event["event_id"]
    candidate["candidate_id"] = str(uuid5(NAMESPACE_URL, f"formation:o2:claim:{example['id']}"))
    for ref in candidate["evidence_refs"]:
        ref["event_id"] = event["event_id"]
    return event, candidate


@pytest.mark.parametrize(
    "case_id,interpretation",
    [
        ("exact-duplicate", False),
        ("explicit-correction", True),
        ("explicit-correction", False),
        ("supported-disagreement", True),
        ("backdated-correction", True),
    ],
)
def test_labelled_comparison_proposals_are_mutated_only_by_engine(
    database, case_id, interpretation
):
    _, examples = load_examples()
    scenarios = {example["id"]: example for example in examples}
    initial = scenarios["new-useful"]
    settings, modules, first_job = setup(database, initial["event"], initial["candidate"])
    with Session(database[1], expire_on_commit=False) as session:
        result = WriteEngine(session, settings, modules).process(first_job)
        assert result.status == "succeeded"
        memory_id = result.memory_ids[0]

    example = scenarios[case_id]
    event, candidate = new_delivery(example)

    class RecordedRelation:
        def compare(self, proposed, record):
            # These labels are bound to this exact fixture pair, not semantic inference.
            assert proposed == candidate
            assert record["memory"]["id"] == str(memory_id)
            assert record["memory"]["version"]["content"] == initial["candidate"]["content"]
            return example["resolution_relation"]

    resolution = SafeResolutionPolicy(RecordedRelation()) if interpretation else None
    settings, modules, job_id = setup(database, event, candidate, resolution=resolution)
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, settings, modules)
        result = engine.process(job_id)
        assert engine.process(job_id).model_dump() == result.model_dump()
        row = session.scalar(select(CaptureCandidate).where(CaptureCandidate.job_id == job_id))
        assert row.admission["outcome"] == example["expected"]["outcome"]
        inspected = MemoryService(session, settings.developer_id).inspect(memory_id)
        if case_id == "exact-duplicate":
            assert row.status == "rejected" and result.memory_ids == []
            assert result.reason_codes == ["DUPLICATE"]
        elif case_id == "explicit-correction" and interpretation:
            assert result.status == "succeeded" and result.memory_ids == [memory_id]
            assert inspected.memory.current_version == 2
            assert inspected.memory.version.content == candidate["content"]
            assert len(inspected.history) == 2
            assert any(
                version.content == initial["candidate"]["content"]
                and version.source.evidence == initial["candidate"]["source"]["evidence"]
                and version.status == "SUPERSEDED"
                for version in inspected.history
            )
            assert [edge.relation for edge in inspected.edges] == ["supersedes"]
        elif case_id == "supported-disagreement":
            assert result.status == "succeeded" and result.memory_ids[0] != memory_id
            versions = session.scalars(select(MemoryVersion)).all()
            assert len(versions) == 2
            assert all(version.decision_state == "contested" for version in versions)
            assert session.scalar(select(MemoryEdge.relation)) == "contradicts"
            assert inspected.memory.version.content == initial["candidate"]["content"]
        else:
            assert result.status == "deferred" and result.memory_ids == []
            reason = (
                "AMBIGUOUS_TIME" if case_id == "backdated-correction" else "INSUFFICIENT_EVIDENCE"
            )
            assert result.reason_codes == [reason]
        if result.status == "deferred" or case_id == "exact-duplicate":
            assert session.scalar(select(func.count()).select_from(Memory)) == 1
            assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 1
            assert inspected.memory.current_version == 1
            assert inspected.memory.version.content == initial["candidate"]["content"]


def test_identical_text_in_different_environments_keeps_both_memories(database):
    _, examples = load_examples()
    initial = next(example for example in examples if example["id"] == "new-useful")
    initial["candidate"]["conditions"] = {"environment": "development"}
    initial["event"]["messages"][0]["content"] += " This applies to development."
    settings, modules, first_job = setup(database, initial["event"], initial["candidate"])
    with Session(database[1], expire_on_commit=False) as session:
        first = WriteEngine(session, settings, modules).process(first_job)
        assert first.status == "succeeded"
    example = next(example for example in examples if example["id"] == "different-environments")
    event, candidate = new_delivery(example)
    settings, modules, second_job = setup(database, event, candidate)
    with Session(database[1], expire_on_commit=False) as session:
        second = WriteEngine(session, settings, modules).process(second_job)
        assert second.status == "succeeded" and second.memory_ids != first.memory_ids
        memories = session.scalars(select(Memory)).all()
        assert {memory.conditions["environment"] for memory in memories} == {
            "development",
            "production",
        }
        assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 2
        assert session.scalar(select(func.count()).select_from(MemoryEdge)) == 0
