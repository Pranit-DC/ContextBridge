from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.engine.errors import EngineError
from contextbridge.engine.indexing import IndexService
from contextbridge.models import EmbeddingModel, MemoryEmbedding, ReindexJob, ReindexTarget
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.integration.retrieval_fakes import RecordedEmbedder, create, embedding, query

pytestmark = pytest.mark.integration


def enqueue(database, memory, request_id=None, **filters):
    with Session(database[1], expire_on_commit=False) as session:
        return IndexService(session, "developer-a").enqueue(
            query(**filters), [str(memory.version.id)], "recorded-v1", 2, str(request_id or uuid4())
        )


def process(database, job_id, provider):
    with Session(database[1], expire_on_commit=False) as session:
        return IndexService(session, "developer-a").process(job_id, provider)


def count(database):
    with Session(database[1]) as session:
        return session.scalar(select(func.count()).select_from(MemoryEmbedding))


def test_reindex_request_replay_and_restart_are_one_vector_write(database):
    target = create(database)
    request_id = uuid4()
    job_id = enqueue(database, target, request_id)
    assert enqueue(database, target, request_id) == job_id
    provider = RecordedEmbedder([[1, 0]])
    assert process(database, job_id, provider)["status"] == "succeeded"
    assert process(database, job_id, provider)["status"] == "succeeded"
    assert len(provider.calls) == 1 and count(database) == 1
    other = create(database, content="Use another database.")
    with pytest.raises(EngineError, match="VERSION_CONFLICT"):
        enqueue(database, other, request_id)


def test_index_identity_cannot_change_dimensions(database):
    target = create(database)
    enqueue(database, target)
    with Session(database[1]) as session:
        with pytest.raises(EngineError, match="INVALID_INPUT"):
            IndexService(session, "developer-a").enqueue(
                query(), [str(target.version.id)], "recorded-v1", 3, str(uuid4())
            )
        session.rollback()
        assert session.get(EmbeddingModel, ("developer-a", "recorded-v1")).dimensions == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"project_id": "other-project"},
        {"owner": "other-owner"},
        {"conditions": {"environment": "production"}},
    ],
)
def test_index_scope_and_conditions_are_checked_before_provider(database, changes):
    target = create(database, **changes)
    with pytest.raises(EngineError, match="OUT_OF_SCOPE"):
        enqueue(database, target)
    assert count(database) == 0


@pytest.mark.parametrize(
    "vectors,dimensions,model_id",
    [
        ([[0, 0]], 2, "recorded-v1"),
        ([[float("nan"), 0]], 2, "recorded-v1"),
        ([[1e40, 0]], 2, "recorded-v1"),
        ([[1e-90, 0]], 2, "recorded-v1"),
        ([[1, 0, 0]], 3, "recorded-v1"),
        ([], 2, "recorded-v1"),
        ([[1, 0]], 2, "wrong-model"),
    ],
)
def test_bad_embedding_shapes_numbers_and_models_fail_safely(
    database, vectors, dimensions, model_id
):
    target = create(database)
    result = process(
        database, enqueue(database, target), RecordedEmbedder(vectors, model_id, dimensions)
    )
    assert result["status"] == "failed" and result["reason_codes"] == ["INVALID_PROVIDER_OUTPUT"]
    assert count(database) == 0


def test_provider_timeout_can_retry_a_saved_batch(database):
    target = create(database)
    job_id = enqueue(database, target)

    class Timeout:
        def embed(self, texts):
            raise TimeoutError("private token and provider response")

    failed = process(database, job_id, Timeout())
    assert failed["status"] == "deferred" and failed["retryable"] is True
    assert failed["reason_codes"] == ["PROVIDER_UNAVAILABLE"]
    assert process(database, job_id, RecordedEmbedder([[1, 0]]))["status"] == "succeeded"


def test_concurrent_redelivery_keeps_one_committed_batch(database):
    target = create(database)
    job_id = enqueue(database, target)
    gate = Barrier(2)

    class ConcurrentEmbedder(RecordedEmbedder):
        def embed(self, texts):
            gate.wait(timeout=10)
            return super().embed(texts)

    providers = [ConcurrentEmbedder([[1, 0]]), ConcurrentEmbedder([[0, 1]])]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda provider: process(database, job_id, provider), providers))
    assert {result["status"] for result in results} == {"succeeded"}
    assert count(database) == 1
    with Session(database[1]) as session:
        stored = session.scalar(select(MemoryEmbedding.vector))
    assert process(database, job_id, RecordedEmbedder([[0.5, 0.5]]))["status"] == "succeeded"
    with Session(database[1]) as session:
        assert session.scalar(select(MemoryEmbedding.vector)) == stored


def test_forget_during_indexing_cancels_job_and_prevents_resurrection(database):
    target = create(database)
    request_id = uuid4()
    job_id = enqueue(database, target, request_id)

    class ForgettingEmbedder(RecordedEmbedder):
        def embed(self, texts):
            with Session(database[1]) as session:
                MemoryService(session, "developer-a").forget(target.id)
            return super().embed(texts)

    result = process(database, job_id, ForgettingEmbedder([[1, 0]]))
    assert result["status"] == "cancelled" and count(database) == 0
    assert process(database, job_id, RecordedEmbedder([[1, 0]]))["status"] == "cancelled"
    with Session(database[1]) as session:
        assert session.get(ReindexJob, job_id).request_fingerprint is None
        assert session.scalar(select(func.count()).select_from(ReindexTarget)) == 0
    with pytest.raises(EngineError, match="CANCELLED"):
        enqueue(database, target, request_id)


def test_updated_source_cannot_put_old_embedding_on_new_version(database):
    target = create(database)
    job_id = enqueue(database, target)

    class UpdatingEmbedder(RecordedEmbedder):
        def embed(self, texts):
            with Session(database[1]) as session:
                MemoryService(session, "developer-a").update(
                    target.id,
                    UpdateMemory(
                        expected_version=1,
                        content="Use SQLite database.",
                        source=target.version.source,
                    ),
                )
            return super().embed(texts)

    assert process(database, job_id, UpdatingEmbedder([[1, 0]]))["status"] == "succeeded"
    with Session(database[1]) as session:
        assert session.scalar(select(MemoryEmbedding.version_id)) == target.version.id
        repository = PostgresRepository(session, "developer-a")
        assert repository.search_channel("semantic", query(), embedding(), 20) == []
        assert repository.warnings == {"EMBEDDING_UNAVAILABLE"}


def test_index_commit_failure_rolls_back_vectors_and_retries(database):
    target = create(database)
    job_id = enqueue(database, target)
    with Session(database[1], expire_on_commit=False) as session:

        class FailingCommitEmbedder(RecordedEmbedder):
            def embed(self, texts):
                def fail(active):
                    raise SQLAlchemyError("private connection diagnostic")

                event.listen(session, "before_commit", fail, once=True)
                return super().embed(texts)

        with pytest.raises(SQLAlchemyError):
            IndexService(session, "developer-a").process(job_id, FailingCommitEmbedder([[1, 0]]))
        session.rollback()
    assert count(database) == 0
    assert process(database, job_id, RecordedEmbedder([[1, 0]]))["status"] == "succeeded"
    assert count(database) == 1


def test_index_job_owner_boundary(database):
    target = create(database)
    job_id = enqueue(database, target)
    with Session(database[1]) as session:
        with pytest.raises(EngineError, match="OUT_OF_SCOPE"):
            IndexService(session, "other-owner").process(job_id, RecordedEmbedder([[1, 0]]))
