"""Actual merged module/store boundaries; recorded backends do not prove model quality."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import WorkerProviders
from contextbridge.contracts import Candidate, CapturedEvent, RetrievalQuery
from contextbridge.db import make_session_factory
from contextbridge.engine.event_reader import EventReader
from contextbridge.engine.indexing import IndexService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider
from contextbridge.models import Memory
from contextbridge.persistence.vectors import vector_available
from contextbridge.retrieval.embedding import GuardedEmbeddingProvider
from contextbridge.retrieval.retriever import RetrievalConfig, Retriever
from contextbridge.retrieval.verifier import EvidenceVerifier
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.background.test_work import work_id
from tests.integration.retrieval_fakes import create, query
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


class RecordedBackend:
    def embed_batch(self, texts):
        return [[1.0, 0.0] for _ in texts]


class RecordedJudge:
    def judge(self, claim, evidence):
        return "supports" if "PostgreSQL" in evidence else "uncertain"


def test_real_formation_through_worker_uses_scoped_event_reader_and_replays(database):
    harness = Harness(database)
    job, candidate, event = harness.enqueue()
    candidate = Candidate.model_validate(candidate).model_dump(mode="json")
    event = CapturedEvent.model_validate(event).model_dump(mode="json")
    sessions = make_session_factory(database[1])
    evidence = RecordedEvidenceVerifier([(event, candidate, "supported")])
    reader = EventReader(sessions, harness.settings)
    modules = ModuleGateway(
        extractor=Extractor(RecordedProvider(event, json.dumps([candidate])), evidence),
        admission=AdmissionPolicy(evidence, reader),
    )
    worker = WorkRunner(sessions, harness.settings, WorkerProviders(modules))
    item = work_id(database, job)
    worker.run(item)
    worker.run(item)
    assert worker.inspect(item)["status"] == "succeeded"
    foreign = Harness(database, owner="developer-b")
    assert EventReader(sessions, foreign.settings)(event["event_id"]) is None
    with Session(database[1]) as db:
        memory = db.scalar(select(Memory))
        assert memory is not None
        MemoryService(db, "developer-a").forget(memory.id)
    assert reader(event["event_id"]) is None
    worker.run(item)
    with Session(database[1]) as db:
        assert db.scalar(select(Memory)) is None


@pytest.mark.parametrize("force_core_only", [False, True])
def test_real_retriever_embedder_verifier_use_filtered_store_and_historical_versions(
    database, monkeypatch, force_core_only
):
    if force_core_only:
        monkeypatch.setattr(
            "contextbridge.persistence.repository.vector_available", lambda db: False
        )
    harness = Harness(database)
    current = create(database, "Use PostgreSQL database.")
    create(database, "Foreign PostgreSQL database.", owner="developer-b")
    create(database, "Other PostgreSQL database.", project_id="other-project")
    embedder = GuardedEmbeddingProvider(RecordedBackend(), model_id="recorded-v1", dimensions=2)
    retriever = Retriever(
        RetrievalConfig(
            embedding_model_id="recorded-v1",
            embedding_dimensions=2,
            verify_types=frozenset({"DECISION"}),
        )
    )
    verifier = EvidenceVerifier(RecordedJudge())
    with Session(database[1], expire_on_commit=False) as db:
        semantic_available = vector_available(db) and not force_core_only
        index = IndexService(db, "developer-a")
        job = index.enqueue(query(), [str(current.version.id)], "recorded-v1", 2, str(uuid4()))
        assert index.process(job, embedder)["status"] == "succeeded"
        service = RetrievalService(
            db, harness.settings, ModuleGateway(retriever=retriever), embedder, verifier
        )
        result = service.search(RetrievalQuery.model_validate(query()))
        assert [card.memory_id for card in result.cards] == [current.id]
        assert result.cards[0].verification == "supported"
        assert result.degraded is (not semantic_available)
        assert result.warnings == ([] if semantic_available else ["EMBEDDING_UNAVAILABLE"])
        instant = datetime.now(UTC)
        MemoryService(db, "developer-a").update(
            current.id,
            UpdateMemory(
                expected_version=1, content="Use SQLite database.", source=current.version.source
            ),
        )
        historical = service.search(RetrievalQuery.model_validate(query(as_of=instant.isoformat())))
        assert historical.cards[0].version_id == current.version.id
        assert historical.cards[0].verification == "supported"
        assert historical.degraded is (not semantic_available)
        assert historical.warnings == ([] if semantic_available else ["EMBEDDING_UNAVAILABLE"])
        MemoryService(db, "developer-a").forget(current.id)
        assert service.search(RetrievalQuery.model_validate(query())).cards == []


def test_forget_during_worker_indexing_cannot_resurrect_vectors(database):
    harness = Harness(database)
    memory = create(database)
    with Session(database[1], expire_on_commit=False) as db:
        job = IndexService(db, "developer-a").enqueue(
            query(), [str(memory.version.id)], "recorded-v1", 2, str(uuid4())
        )

    class ForgetBackend(RecordedBackend):
        def embed_batch(self, texts):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").forget(memory.id)
            return super().embed_batch(texts)

    provider = GuardedEmbeddingProvider(ForgetBackend(), model_id="recorded-v1", dimensions=2)
    worker = WorkRunner(
        make_session_factory(database[1]), harness.settings, WorkerProviders(embedder=provider)
    )
    item = work_id(database, job)
    worker.run(item)
    worker.run(item)
    assert worker.inspect(item)["status"] == "cancelled"
    with Session(database[1]) as db:
        assert db.get(Memory, memory.id) is None
