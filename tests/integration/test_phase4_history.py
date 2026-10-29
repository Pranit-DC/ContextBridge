"""Actual pgvector history with synthetic Cloudflare HTTP vectors, not model quality."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.contracts import RetrievalQuery
from contextbridge.db import make_session_factory
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.engine.indexing import IndexService
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.management import RestoreMemory, RetireMemory
from contextbridge.models import MemoryEmbedding, ReindexJob
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.persistence.vectors import vector_available
from contextbridge.retrieval.cloudflare import DIMENSIONS, MODEL_ID, CloudflareEmbeddingBackend
from contextbridge.runtime import IntegrationBackends, assemble
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from scripts.v1.budget import BudgetTransport, Ledger
from tests.integration.retrieval_fakes import create, query
from tests.retrieval.test_cloudflare import BASE_URL, SYNTHETIC_KEY, configuration, response

pytestmark = pytest.mark.integration


def test_discovery_indexes_correction_restoration_and_semantic_history_with_retirement_gap(
    database, tmp_path
):
    configured = configuration(
        database_url=database[0], developer_id="developer-a", capture_project_id="contextbridge"
    )
    sessions = make_session_factory(database[1])
    path = tmp_path / "offline-cloudflare-ledger.sqlite"
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200, json=response([[1.0] + [0.0] * (DIMENSIONS - 1) for _ in body["input"]])
        )

    backend = CloudflareEmbeddingBackend(
        api_key=SYNTHETIC_KEY,
        base_url=BASE_URL,
        transport=BudgetTransport(path, "cloudflare", transport=httpx.MockTransport(handle)),
    )
    providers = assemble(configured, sessions, IntegrationBackends(embedding_backend=backend))
    initial = create(
        database,
        "Use PostgreSQL database.",
        valid_from=(datetime.now(UTC) - timedelta(days=2)).isoformat(),
    )

    def index_current():
        assert queue_missing_indexes(sessions, configured) == 1
        assert queue_missing_indexes(sessions, configured) == 0
        with Session(database[1]) as db:
            pending = list(db.scalars(select(ReindexJob).where(ReindexJob.status == "queued")))
            assert len(pending) == 1
            assert (
                IndexService(db, "developer-a").process(pending[0].id, providers.embedder)["status"]
                == "succeeded"
            )

    index_current()
    old_time = datetime.now(UTC)
    with Session(database[1]) as db:
        service = MemoryService(db, "developer-a")
        corrected = service.update(
            initial.id,
            UpdateMemory(
                expected_version=1, content="Use SQLite database.", source=initial.version.source
            ),
        )
    index_current()
    corrected_time = datetime.now(UTC)
    with Session(database[1]) as db:
        service = MemoryService(db, "developer-a")
        service.retire(
            initial.id,
            RetireMemory(scope="project", project_id="contextbridge", expected_version=2),
        )
        gap = datetime.now(UTC)
        assert queue_missing_indexes(sessions, configured) == 0
        restored = service.restore(
            initial.id,
            RestoreMemory(
                scope="project",
                project_id="contextbridge",
                expected_version=2,
                source_version=2,
                source=initial.version.source.model_copy(
                    update={"evidence": "I confirm SQLite applies again."}
                ),
            ),
        )
    index_current()
    with Session(database[1]) as db:
        vectors = list(db.scalars(select(MemoryEmbedding)))
        assert {v.version_id for v in vectors} == {
            initial.version.id,
            corrected.version.id,
            restored.memory.version.id,
        }
        semantic = vector_available(db)
        repository = PostgresRepository(db, "developer-a")
        embed = {
            "model_id": MODEL_ID,
            "dimensions": DIMENSIONS,
            "vector": [1.0] + [0.0] * (DIMENSIONS - 1),
        }
        for instant, expected in [
            (old_time, initial.version),
            (corrected_time, corrected.version),
            (gap, None),
            (None, restored.memory.version),
        ]:
            q = query(
                query="Which datastore was selected?",
                as_of=instant.isoformat() if instant else None,
            )
            matches = repository.search_channel("semantic", q, embed, 3)
            assert [m["record"]["memory"]["version"]["id"] for m in matches] == (
                [str(expected.id)] if semantic and expected else []
            )
            result = RetrievalService(
                db, configured, providers.modules, providers.embedder, providers.verifier
            ).search(RetrievalQuery.model_validate(q))
            assert [c.version_id for c in result.cards] == (
                [expected.id] if semantic and expected else []
            )
        history = MemoryService(db, "developer-a").inspect(initial.id).history
        assert [v.number for v in history] == [1, 2, 3]
        assert [v.status for v in history] == ["SUPERSEDED", "SUPERSEDED", "ACTIVE"]
        assert history[1].valid_to < history[2].valid_from
    assert len(requests) == 7  # three document indexes and four historical/current query embeddings
    assert Ledger(path).snapshot() == {"calls": {"groq": 0, "cloudflare": 7}, "stopped": False}
