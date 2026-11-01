import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
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


def test_exact_repeated_live_style_candidate_is_rejected_without_new_version(database):
    harness = Harness(database)
    text = "Use PostgreSQL as primary database for contextbridge."
    first, _, event_a = harness.enqueue(text, time=datetime.now(UTC))
    second, _, event_b = harness.enqueue(text, time=datetime.now(UTC))
    events = {event_a["event_id"]: event_a, event_b["event_id"]: event_b}

    class Support:
        def verify(self, candidate, event):
            return "supported"

    modules = ModuleGateway(
        extractor=harness.extractor,
        admission=AdmissionPolicy(Support(), events.get),
        resolution=SafeResolutionPolicy(),
    )
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    assert harness.process(first, modules).status == "succeeded"
    result = harness.process(second, modules)
    assert result.status == "succeeded" and result.reason_codes == ["DUPLICATE"]
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


@pytest.mark.parametrize("variation", ["conditions", "type"])
def test_verbatim_sole_source_with_changed_metadata_defers_without_model_calls(database, variation):
    harness = Harness(database)
    first, _, _ = harness.enqueue("Use PostgreSQL.", time=datetime.now(UTC))
    assert harness.process(first).status == "succeeded"
    second, candidate, event = harness.enqueue("Use PostgreSQL.", time=datetime.now(UTC))
    if variation == "conditions":
        candidate["conditions"] = {"environment": "production"}
    else:
        candidate["type"] = "FACT"
    harness.extractor.outputs[event["event_id"]] = [candidate]
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})

    class ForbiddenAdmission:
        def assess(self, candidate, context):
            raise AssertionError("Changed metadata requires new evidence before a model call")

    result = harness.process(
        second, ModuleGateway(extractor=harness.extractor, admission=ForbiddenAdmission())
    )
    assert result.status == "deferred" and result.reason_codes == ["INSUFFICIENT_EVIDENCE"]
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_new_evidenced_condition_can_coexist_with_same_text(database):
    harness = Harness(database)
    first, _, _ = harness.enqueue("Use PostgreSQL.", time=datetime.now(UTC))
    harness.process(first)
    second, _, _ = harness.enqueue(
        "Use PostgreSQL.",
        evidence="In production, use PostgreSQL.",
        conditions={"environment": "production"},
        time=datetime.now(UTC),
    )
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    assert harness.process(second).status == "succeeded"
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 2


def test_reclassification_cannot_reactivate_retired_verbatim_source(database):
    from contextbridge.management import RetireMemory

    harness = Harness(database)
    first, _, _ = harness.enqueue("Use PostgreSQL.", time=datetime.now(UTC))
    result = harness.process(first)
    with Session(database[1]) as db:
        MemoryService(db, harness.settings.developer_id).retire(
            result.memory_ids[0],
            RetireMemory(scope="project", project_id="contextbridge", expected_version=1),
        )
    second, candidate, event = harness.enqueue("Use PostgreSQL.", time=datetime.now(UTC))
    candidate["type"] = "FACT"
    harness.extractor.outputs[event["event_id"]] = [candidate]
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    assert harness.process(second).status == "deferred"
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_metadata_ambiguity_is_rechecked_after_saved_create_proposal(database):
    from tests.integration.write_fakes import Admit

    harness = Harness(database)
    job, candidate, _ = harness.enqueue(
        "Use PostgreSQL.", conditions={"environment": "production"}, time=datetime.now(UTC)
    )

    class ConcurrentSave(Admit):
        def assess(self, candidate, context):
            with Session(database[1]) as db:
                MemoryService(db, harness.settings.developer_id).create(
                    CreateMemory(
                        request_id=uuid4(),
                        scope="project",
                        project_id="contextbridge",
                        type="DECISION",
                        content=candidate["content"],
                        source=candidate["source"],
                        conditions={},
                    )
                )
            return super().assess(candidate, context)

    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    result = harness.process(
        job, ModuleGateway(extractor=harness.extractor, admission=ConcurrentSave())
    )
    assert result.status == "deferred"
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 1
