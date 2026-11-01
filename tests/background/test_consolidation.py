from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import WorkerProviders
from contextbridge.db import make_session_factory
from contextbridge.engine.consolidation import ConsolidationService
from contextbridge.engine.errors import EngineError
from contextbridge.engine.indexing import IndexService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.models import (
    ConsolidationJob,
    ConsolidationSource,
    Memory,
    MemoryEdge,
    MemoryEmbedding,
    WorkItem,
)
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.background.test_work import work_id
from tests.integration.retrieval_fakes import RecordedEmbedder, create, query
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


class Proposals:
    def __init__(self):
        self.calls = 0
        self.id = str(uuid4())

    def propose(self, records):
        self.calls += 1
        refs = [r["memory"]["version"]["source"] for r in records]
        refs = [{key: ref[key] for key in ["agent", "session", "interaction"]} for ref in refs]
        refs = list({tuple(sorted(ref.items())): ref for ref in refs}.values())
        return [
            {
                "schema_version": 1,
                "proposal_id": self.id,
                "source_version_ids": [r["memory"]["version"]["id"] for r in records],
                "summary": "The database uses PostgreSQL; keep its backup policy.",
                "source_refs": refs,
                "scope": "project",
                "project_id": "contextbridge",
                "conditions": {},
            }
        ]


def setup(database, **settings):
    harness = Harness(database, **settings)
    sources = [create(database), create(database, "Keep daily backups.")]
    with Session(database[1], expire_on_commit=False) as db:
        job = ConsolidationService(db, harness.settings).enqueue(
            query(), [str(s.version.id) for s in sources], str(uuid4())
        )
    return harness, sources, job


def process(database, harness, job, provider):
    with Session(database[1], expire_on_commit=False) as db:
        return ConsolidationService(db, harness.settings).process(job, provider)


def test_consolidation_preserves_originals_edges_evidence_and_replay(database):
    harness, sources, job = setup(database)
    provider = Proposals()
    first = process(database, harness, job, provider)
    assert first["status"] == "succeeded" and len(first["memory_ids"]) == 1
    assert process(database, harness, job, provider) == first
    assert provider.calls == 1
    with Session(database[1]) as db:
        summary = MemoryService(db, "developer-a").inspect(UUID(first["memory_ids"][0]))
        assert summary.memory.type == "STATE"
        assert summary.memory.version.source == sources[0].version.source
        assert len(summary.edges) == 2
        assert db.scalar(select(func.count()).select_from(Memory)) == 3
        assert db.scalar(select(ConsolidationJob.proposals)) is None


@pytest.mark.parametrize(
    "change", ["scope", "conditions", "source", "refs", "duplicate", "secret", "shape"]
)
def test_invalid_consolidation_proposals_fail_without_partial_summary(database, change):
    harness, _, job = setup(database)

    class Invalid(Proposals):
        def propose(self, records):
            raw = super().propose(records)
            if change == "scope":
                raw[0]["project_id"] = "other"
            elif change == "conditions":
                raw[0]["conditions"] = {"env": "test"}
            elif change == "source":
                raw[0]["source_version_ids"][0] = str(uuid4())
            elif change == "refs":
                raw[0]["source_refs"][0]["session"] = "forged"
            elif change == "duplicate":
                raw.append(deepcopy(raw[0]))
            elif change == "secret":
                raw[0]["summary"] = "api_key=sk-live-abcdefghijklmnopqrstuvwxyz123456789"
            else:
                return {"summary": "invalid"}
            return raw

    result = process(database, harness, job, Invalid())
    assert result["status"] == "failed" and result["reason_codes"] == ["INVALID_PROVIDER_OUTPUT"]
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 2
        assert db.scalar(select(func.count()).select_from(MemoryEdge)) == 0


def test_updated_source_during_proposal_rejects_stale_summary(database):
    harness, sources, job = setup(database)

    class Update(Proposals):
        def propose(self, records):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").update(
                    sources[0].id,
                    UpdateMemory(
                        expected_version=1, content="Use SQLite.", source=sources[0].version.source
                    ),
                )
            return super().propose(records)

    result = process(database, harness, job, Update())
    assert result["status"] == "failed" and result["reason_codes"] == ["VERSION_CONFLICT"]
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 2


def test_forget_during_consolidation_erases_saved_sources_and_outbox(database):
    harness, sources, job = setup(database)

    class Forget(Proposals):
        def propose(self, records):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").forget(sources[0].id)
            return super().propose(records)

    worker = WorkRunner(
        make_session_factory(database[1]),
        harness.settings,
        WorkerProviders(ModuleGateway(consolidator=Forget())),
    )
    item = work_id(database, job)
    worker.run(item)
    worker.run(item)
    assert worker.inspect(item)["status"] == "cancelled"
    with Session(database[1]) as db:
        saved = db.get(ConsolidationJob, job)
        assert saved.proposals is saved.request_fingerprint is None
        assert saved.result_memory_ids == []
        assert db.scalar(select(ConsolidationSource)) is None
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_forget_removes_multi_source_summary_and_its_vector(database):
    harness, sources, job = setup(database)
    result = process(database, harness, job, Proposals())
    summary_id = UUID(result["memory_ids"][0])
    with Session(database[1], expire_on_commit=False) as db:
        summary = MemoryService(db, "developer-a").inspect(summary_id).memory
        index = IndexService(db, "developer-a")
        index_job = index.enqueue(
            query(), [str(summary.version.id)], "recorded-v1", 2, str(uuid4())
        )
        assert index.process(index_job, RecordedEmbedder([[1, 0]]))["status"] == "succeeded"
        MemoryService(db, "developer-a").forget(sources[0].id)
    with Session(database[1]) as db:
        assert db.get(Memory, summary_id) is None
        assert db.get(Memory, sources[1].id) is not None
        assert db.scalar(select(MemoryEmbedding)) is None
        assert db.scalar(select(MemoryEdge)) is None
        assert db.get(ConsolidationJob, job).request_fingerprint is None
        assert db.get(WorkItem, work_id(database, job)).status == "cancelled"


def test_saved_proposals_survive_rollback_without_provider_reinterpretation(database):
    harness, _, job = setup(database)
    provider = Proposals()
    sessions = make_session_factory(database[1])
    with sessions() as db:

        def fail_summary_flush(session, flush_context, instances):
            if any(isinstance(item, Memory) for item in session.new):
                raise SQLAlchemyError("private DB error")

        event.listen(db, "before_flush", fail_summary_flush)
        with pytest.raises(SQLAlchemyError):
            ConsolidationService(db, harness.settings).process(job, provider)
    result = process(database, harness, job, provider)
    assert result["status"] == "succeeded" and provider.calls == 1


def test_consolidation_selection_scope_conditions_and_retention(database):
    harness, sources, job = setup(database, candidate_retention_seconds=60)
    foreign = create(database, owner="developer-b")
    with Session(database[1]) as db, pytest.raises(EngineError):
        ConsolidationService(db, harness.settings).enqueue(
            query(), [str(foreign.version.id)], str(uuid4())
        )
    with database[1].begin() as db:
        db.execute(
            update(ConsolidationJob)
            .where(ConsolidationJob.id == job)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    provider = Proposals()
    assert process(database, harness, job, provider)["status"] == "cancelled"
    assert provider.calls == 0
    with Session(database[1]) as db:
        assert db.get(Memory, sources[0].id) is not None
