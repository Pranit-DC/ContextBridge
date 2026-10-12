import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.contracts import Candidate, CapturedEvent
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.resolution import SafeResolutionPolicy
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider
from contextbridge.models import CaptureCandidate, Memory
from contextbridge.schemas import CreateMemory
from contextbridge.service import MemoryService
from tests.integration.write_fakes import Harness, Relation

pytestmark = pytest.mark.integration


def test_semantic_correction_can_target_keyless_explicit_save_with_version_fence(database):
    harness = Harness(database)
    now = datetime.now(UTC)
    job, candidate, _ = harness.enqueue("Use SQLite instead.", time=now - timedelta(hours=1))
    with Session(database[1], expire_on_commit=False) as db:
        explicit = MemoryService(db, harness.settings.developer_id).create(
            CreateMemory(
                request_id=uuid4(),
                scope="project",
                project_id="contextbridge",
                type="DECISION",
                content="Use PostgreSQL.",
                source=candidate["source"],
                valid_from=now - timedelta(days=1),
            )
        )
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    harness.set_relation("correction")
    result = harness.process(job)
    assert result.status == "succeeded" and result.memory_ids == [explicit.id]
    with Session(database[1]) as db:
        inspection = MemoryService(db, harness.settings.developer_id).inspect(explicit.id)
        assert [v.content for v in inspection.history] == ["Use PostgreSQL.", "Use SQLite instead."]
        assert db.get(Memory, explicit.id).claim_key is None


def test_source_bound_uncertainty_remains_pending_without_writing_memory(database):
    harness = Harness(database)
    job, candidate, event = harness.enqueue()
    candidate = Candidate.model_validate(candidate).model_dump(mode="json")
    event = CapturedEvent.model_validate(event).model_dump(mode="json")
    verifier = RecordedEvidenceVerifier([(event, candidate, "uncertain")])
    modules = ModuleGateway(
        extractor=Extractor(
            RecordedProvider(event, json.dumps([candidate])), verifier, admission_checks=True
        ),
        admission=AdmissionPolicy(verifier, lambda _: event),
        resolution=SafeResolutionPolicy(Relation("uncertain")),
    )
    result = harness.process(job, modules)
    assert result.status == "deferred"
    with Session(database[1]) as db:
        assert db.scalar(select(Memory)) is None
        row = db.scalar(select(CaptureCandidate))
        assert row.status == "deferred"
        assert row.reason_codes == ["INSUFFICIENT_EVIDENCE"]
