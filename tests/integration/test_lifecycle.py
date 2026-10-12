from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import WorkerProviders
from contextbridge.contracts import CapturedEvent
from contextbridge.db import make_session_factory
from contextbridge.engine.indexing import IndexService
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.resolution import SafeResolutionPolicy
from contextbridge.management import RestoreMemory, RetireMemory
from contextbridge.models import (
    CaptureCandidate,
    CaptureEvent,
    ConsolidationJob,
    Memory,
    MemoryEmbedding,
)
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService, MemoryServiceError
from tests.background.test_consolidation import Proposals, process, setup
from tests.background.test_work import work_id
from tests.engine.fakes import fixture
from tests.integration.retrieval_fakes import RecordedEmbedder, create, index, query
from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def retirement(**changes):
    return {"scope": "project", "project_id": "contextbridge", "expected_version": 1, **changes}


def restore_body(**changes):
    return {
        **retirement(),
        "source_version": 1,
        "source": payload()["source"]
        | {"interaction": "restore", "evidence": "I confirm this memory applies again."},
        **changes,
    }


def search_query(**changes):
    return {
        k: v
        for k, v in query(**({"query": "PostgreSQL"} | changes)).items()
        if k != "schema_version"
    }


def test_api_retirement_restore_preserves_history_and_inactive_gap(client):
    saved = client.post(
        "/v1/memories", json=payload(valid_from=(datetime.now(UTC) - timedelta(days=1)).isoformat())
    ).json()
    memory_id = saved["id"]
    before = datetime.now(UTC).isoformat()
    retired = client.post(f"/v1/memories/{memory_id}/retire", json=retirement())
    assert retired.status_code == 200
    retired_at = retired.json()["retired_at"]
    assert client.post("/v1/memories/search", json=search_query()).json() == []
    assert (
        client.post("/v1/memories/search", json=search_query(as_of=before)).json()[0]["id"]
        == memory_id
    )
    listing = client.post(
        "/v1/inspection/retired", json={"scope": "project", "project_id": "contextbridge"}
    ).json()
    assert listing["items"][0]["memory"]["id"] == memory_id
    gap = datetime.now(UTC).isoformat()
    assert (
        client.put(
            f"/v1/memories/{memory_id}",
            json={"expected_version": 1, "content": "Changed.", "source": payload()["source"]},
        ).status_code
        == 409
    )
    restored = client.post(f"/v1/memories/{memory_id}/restore", json=restore_body())
    assert restored.status_code == 200 and restored.json()["memory"]["current_version"] == 2
    assert restored.json()["memory"]["version"]["source"]["interaction"] == "restore"
    history = client.get(f"/v1/memories/{memory_id}").json()["history"]
    assert len(history) == 2 and history[0]["valid_to"] == retired_at
    assert history[0]["source"] == saved["version"]["source"]
    assert history[0]["content"] == history[1]["content"] == saved["version"]["content"]
    assert client.post("/v1/memories/search", json=search_query(as_of=gap)).json() == []
    assert client.post(f"/v1/memories/{memory_id}/restore", json=restore_body()).status_code == 409
    assert client.delete(f"/v1/memories/{memory_id}").status_code == 204
    assert (
        client.post(
            f"/v1/memories/{memory_id}/restore", json=restore_body(expected_version=2)
        ).status_code
        == 404
    )


def test_management_scope_versions_secret_errors_and_retired_pagination(client, clients):
    ids = [client.post("/v1/memories", json=payload()).json()["id"] for _ in range(3)]
    foreign = clients("another-owner")
    for memory_id in ids:
        assert (
            foreign.post(f"/v1/memories/{memory_id}/retire", json=retirement()).status_code == 404
        )
        assert (
            client.post(
                f"/v1/memories/{memory_id}/retire", json=retirement(project_id="another-project")
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/v1/memories/{memory_id}/retire", json=retirement(expected_version=2)
            ).status_code
            == 409
        )
        assert client.post(f"/v1/memories/{memory_id}/retire", json=retirement()).status_code == 200
    body = {"scope": "project", "project_id": "contextbridge", "limit": 2}
    page = client.post("/v1/inspection/retired", json=body).json()
    assert len(page["items"]) == 2 and page["next_cursor"] is not None
    next_page = client.post(
        "/v1/inspection/retired", json=body | {"cursor": page["next_cursor"]}
    ).json()
    assert len(next_page["items"]) == 1
    assert {x["memory"]["id"] for x in page["items"] + next_page["items"]} == set(ids)
    assert foreign.post("/v1/inspection/retired", json=body).json()["items"] == []
    secret = "sk-" + "s" * 40
    response = client.post(f"/v1/memories/{ids[0]}/restore", json=restore_body(**{secret: "extra"}))
    assert response.status_code == 422 and secret not in response.text
    response = client.post(
        f"/v1/memories/{ids[0]}/restore",
        json=restore_body(source=payload()["source"] | {"evidence": secret}),
    )
    assert response.status_code == 422 and secret not in response.text


def test_retirement_closes_derived_summaries_preserves_vectors_and_forget_erases_all(database):
    harness, sources, job = setup(database)
    result = process(database, harness, job, Proposals())
    summary_id = UUID(result["memory_ids"][0])
    index(database, sources, [[1.0, 0.0], [0.0, 1.0]])
    with Session(database[1]) as db:
        service = MemoryService(db, "developer-a")
        retired = service.retire(sources[0].id, RetireMemory(**retirement()))
        assert retired.affected_memories == 2
        assert service.get_memory(summary_id).retired_at is not None
        assert service.get_memory(sources[1].id).retired_at is None
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 2
        with pytest.raises(MemoryServiceError, match="consolidate again"):
            service.restore(summary_id, RestoreMemory(**restore_body()))
        db.rollback()
        service.restore(sources[0].id, RestoreMemory(**restore_body()))
        assert service.get_memory(summary_id).retired_at is not None
        service.forget(sources[0].id)
        assert db.get(Memory, summary_id) is None
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1
        assert db.get(ConsolidationJob, job).proposals is None


def test_retirement_during_indexing_cancels_commit_and_new_version_is_indexable(database):
    target = create(database)
    with Session(database[1], expire_on_commit=False) as db:
        indexer = IndexService(db, "developer-a")
        job = indexer.enqueue(query(), [str(target.version.id)], "recorded-v1", 2, str(uuid4()))

    class RetiringEmbedder(RecordedEmbedder):
        def embed(self, texts):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").retire(target.id, RetireMemory(**retirement()))
            return super().embed(texts)

    with Session(database[1]) as db:
        assert (
            IndexService(db, "developer-a").process(job, RetiringEmbedder([[1.0, 0.0]]))["status"]
            == "cancelled"
        )
        assert db.scalar(select(MemoryEmbedding)) is None
        restored = (
            MemoryService(db, "developer-a")
            .restore(target.id, RestoreMemory(**restore_body()))
            .memory
        )
    index(database, [restored], [[1.0, 0.0]])


def test_retirement_during_capture_cancels_scope_but_preserves_saved_memory(database):
    harness = Harness(database)
    stored = create(database)
    job, _, _ = harness.enqueue()
    other = Harness(database, project="other-project")
    other_job, _, _ = other.enqueue()

    class RetiringExtractor:
        def extract(self, event):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").retire(stored.id, RetireMemory(**retirement()))
            return harness.extractor.extract(event)

    runner = WorkRunner(
        make_session_factory(database[1]),
        harness.settings,
        WorkerProviders(
            ModuleGateway(extractor=RetiringExtractor(), admission=harness.modules.admission)
        ),
    )
    item = work_id(database, job)
    runner.run(item)
    runner.run(item)
    assert runner.inspect(item)["status"] == "cancelled"
    with Session(database[1]) as db:
        assert db.get(Memory, stored.id).retired_at is not None
        assert db.scalar(select(func.count()).select_from(Memory)) == 1
        assert (
            db.scalar(select(CaptureCandidate.payload).where(CaptureCandidate.job_id == UUID(job)))
            is None
        )
        assert (
            db.scalar(
                select(CaptureEvent.payload).where(CaptureEvent.project_id == "other-project")
            )
            is not None
        )
    other_runner = WorkRunner(make_session_factory(database[1]), other.settings, None)
    assert other_runner.inspect(work_id(database, other_job))["status"] == "queued"


def test_retirement_during_consolidation_cancels_proposals_and_replay(database):
    harness, sources, job = setup(database)

    class RetiringProposals(Proposals):
        def propose(self, records):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").retire(sources[0].id, RetireMemory(**retirement()))
            return super().propose(records)

    assert process(database, harness, job, RetiringProposals())["status"] == "cancelled"
    assert process(database, harness, job, Proposals())["status"] == "cancelled"
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 2
        assert db.get(ConsolidationJob, job).proposals is None


def test_stale_session_cannot_retire_an_unobserved_update(database):
    target = create(database)
    with Session(database[1]) as stale, Session(database[1]) as updating:
        service = MemoryService(stale, "developer-a")
        service.get_memory(target.id)
        MemoryService(updating, "developer-a").update(
            target.id,
            UpdateMemory(expected_version=1, content="Use SQLite.", source=target.version.source),
        )
        with pytest.raises(MemoryServiceError, match="changed"):
            service.retire(target.id, RetireMemory(**retirement()))


def test_new_import_does_not_reactivate_retired_claim_but_unrelated_fact_can_be_saved(database):
    harness = Harness(database)
    target = create(database, "Use PostgreSQL database.")
    with Session(database[1]) as db:
        MemoryService(db, "developer-a").retire(target.id, RetireMemory(**retirement()))
    job, _, _ = harness.enqueue("PostgreSQL is the project's database.")
    unrelated_job, _, _ = harness.enqueue("Keep daily backups.")
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    harness.set_relation("same")
    assert harness.process(job).status == "deferred"
    harness.set_relation("unrelated")
    assert harness.process(unrelated_job).status == "succeeded"
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 2
        assert db.get(Memory, target.id).retired_at is not None


def test_source_correction_retires_stale_summary_but_keeps_its_history_and_originals(database):
    harness, sources, job = setup(database)
    result = process(database, harness, job, Proposals())
    summary_id = UUID(result["memory_ids"][0])
    before = datetime.now(UTC)
    with Session(database[1]) as db:
        service = MemoryService(db, "developer-a")
        service.update(
            sources[0].id,
            UpdateMemory(
                expected_version=1, content="Use SQLite.", source=sources[0].version.source
            ),
        )
        assert service.get_memory(summary_id).retired_at is not None
        assert service.get_memory(sources[0].id).retired_at is None
        assert len(service.inspect(summary_id).history) == 1
        from contextbridge.schemas import SearchMemories

        current = service.search(SearchMemories.model_validate(search_query()))
        historical = service.search(SearchMemories.model_validate(search_query(as_of=before)))
        assert summary_id not in {item.id for item in current}
        assert summary_id in {item.id for item in historical}
        assert db.get(Memory, sources[1].id).retired_at is None


def test_correction_in_same_import_does_not_cancel_its_own_prior_summary_reference(database):
    harness, sources, job = setup(database)
    result = process(database, harness, job, Proposals())
    summary_id = UUID(result["memory_ids"][0])
    with Session(database[1]) as db:
        summary = MemoryService(db, "developer-a").inspect(summary_id).memory.version.content
    event = fixture("captured-event")
    event.update(event_id=str(uuid4()), occurred_at=datetime.now(UTC).isoformat())
    event["messages"] = [
        {"message_id": "summary", "role": "user", "content": summary},
        {"message_id": "correction", "role": "user", "content": "Use SQLite instead."},
    ]
    candidates = []
    for kind, text, message in [
        ("STATE", summary, "summary"),
        ("DECISION", "Use SQLite instead.", "correction"),
    ]:
        candidate = fixture("candidate")
        candidate.update(
            candidate_id=str(uuid4()),
            event_id=event["event_id"],
            type=kind,
            content=text,
            conditions={},
            valid_from=event["occurred_at"],
        )
        candidate["source"]["evidence"] = text
        candidate["evidence_refs"] = [{"event_id": event["event_id"], "message_id": message}]
        candidates.append(candidate)
    harness.extractor.outputs[event["event_id"]] = candidates

    class Relation:
        def compare(self, candidate, record):
            return "correction" if record["memory"]["id"] == str(sources[0].id) else "unrelated"

    harness.modules = ModuleGateway(
        extractor=harness.extractor,
        admission=harness.modules.admission,
        resolution=SafeResolutionPolicy(Relation()),
    )
    harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
    with Session(database[1]) as db:
        captured = IngestionService(db, harness.settings).ingest(
            CapturedEvent.model_validate(event)
        )
    assert harness.process(str(captured.job_id)).status == "succeeded"
    with Session(database[1]) as db:
        assert db.get(Memory, sources[0].id).current_version == 2
        assert db.get(Memory, summary_id).retired_at is not None
