"""Real PostgreSQL/engine integration with explicitly recorded formation providers."""

import json
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import CapturedEvent
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.write import WriteEngine
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider
from contextbridge.models import CaptureCandidate, CaptureEvent, Memory, MemoryVersion
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN

pytestmark = pytest.mark.integration


def setup(database, event, candidate, *, admission_support="supported"):
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
