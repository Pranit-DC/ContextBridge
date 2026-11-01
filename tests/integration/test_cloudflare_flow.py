"""Real API/MCP/PG/runtime with synthetic Cloudflare HTTP, never live credentials."""

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import Client
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import load_providers
from contextbridge.db import make_session_factory
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.mcp_adapter.config import MCPSettings
from contextbridge.mcp_adapter.gateway import MemoryGateway
from contextbridge.mcp_adapter.server import create_server
from contextbridge.models import CaptureJob, MemoryEmbedding, WorkItem
from contextbridge.persistence.vectors import vector_available
from contextbridge.retrieval.cloudflare import DIMENSIONS, CloudflareEmbeddingBackend
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN
from tests.integration.retrieval_fakes import create, query
from tests.integration.write_fakes import Harness
from tests.retrieval.test_cloudflare import configuration, response
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def synthetic_backend(monkeypatch, handler):
    monkeypatch.setattr(
        "contextbridge.runtime.CloudflareEmbeddingBackend",
        lambda **options: CloudflareEmbeddingBackend(
            **options, transport=httpx.MockTransport(handler)
        ),
    )


def worker(database):
    settings = configuration(
        database_url=database[0], developer_id="developer-a", capture_project_id="contextbridge"
    )
    sessions = make_session_factory(database[1])
    return WorkRunner(sessions, settings, load_providers(settings, sessions))


def process_indexes(database, runner):
    assert queue_missing_indexes(runner.sessions, runner.settings) >= 0
    with Session(database[1]) as db:
        items = list(db.scalars(select(WorkItem.id).where(WorkItem.kind == "reindex")))
    for item in items:
        runner.run(item)


def test_index_restart_fresh_mcp_correction_history_scope_and_forgetting(database, monkeypatch):
    calls = []

    def handler(request):
        texts = json.loads(request.content)["input"]
        calls.append(texts)
        vectors = []
        for text in texts:
            direction = 0 if "PostgreSQL" in text or "durable datastore" in text else 1
            vector = [0.0] * DIMENSIONS
            vector[direction] = 1.0
            vectors.append(vector)
        return httpx.Response(200, json=response(vectors))

    synthetic_backend(monkeypatch, handler)
    runner = worker(database)
    target = create(database)
    create(database, content="Format logs as JSON.")
    create(database, content="Use PostgreSQL foreign project.", project_id="foreign")
    create(database, content="Use PostgreSQL foreign owner.", owner="developer-b")
    assert queue_missing_indexes(runner.sessions, runner.settings) == 2
    # Assembly is fresh after accepted jobs were durably queued.
    runner = worker(database)
    process_indexes(database, runner)
    documents = len(calls)
    process_indexes(database, worker(database))
    assert len(calls) == documents  # no re-embedding after restart/replay
    with Session(database[1]) as db:
        semantic = vector_available(db)
    phrase = "durable datastore" if semantic else "PostgreSQL"
    historic = datetime.now(UTC).isoformat()
    with TestClient(
        create_app(runner.settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    ) as api:
        result = api.post("/v1/retrieval/search", json=query(query=phrase, limit=1))
        assert result.status_code == 200 and result.json()["degraded"] is (not semantic)
        assert result.json()["cards"][0]["memory_id"] == str(target.id)
        assert "Instruct:" in calls[-1][0]

        def agent(name):
            return Client(
                create_server(
                    MemoryGateway(
                        MCPSettings(
                            _env_file=None,
                            api_token=TEST_TOKEN,
                            project_id="contextbridge",
                            agent_id=name,
                        ),
                        httpx.ASGITransport(app=api.app),
                    )
                )
            )

        async def agents():
            async with agent("codex") as first:
                found = await first.call_tool("memory_retrieve", {"query": phrase, "limit": 1})
                assert found.structured_content["cards"][0]["memory_id"] == str(target.id)
                corrected = await first.call_tool(
                    "memory_update",
                    {
                        "memory_id": str(target.id),
                        "expected_version": 1,
                        "content": "Use SQLite database.",
                        "source": {
                            "kind": "user",
                            "interaction": "turn-2",
                            "evidence": "Use SQLite database.",
                        },
                    },
                )
                assert not corrected.is_error
            assert queue_missing_indexes(runner.sessions, runner.settings) == 1
            process_indexes(database, worker(database))
            async with agent("claude-code") as fresh:
                found = await fresh.call_tool("memory_retrieve", {"query": "SQLite", "limit": 1})
                assert found.structured_content["cards"][0]["version_number"] == 2
                old = await fresh.call_tool(
                    "memory_retrieve", {"query": phrase, "as_of": historic, "limit": 1}
                )
                assert old.structured_content["cards"][0]["version_number"] == 1
                forgotten = await fresh.call_tool("memory_forget", {"memory_id": str(target.id)})
                assert not forgotten.is_error
            async with agent("after-forget") as fresh:
                found = await fresh.call_tool("memory_retrieve", {"query": "durable datastore"})
                assert all(
                    c["memory_id"] != str(target.id) for c in found.structured_content["cards"]
                )

        asyncio.run(agents())
    process_indexes(database, worker(database))
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1
        assert db.scalar(select(MemoryEmbedding.dimensions)) == DIMENSIONS


def test_embedding_only_worker_does_not_publish_claim_or_backfill_capture(database, monkeypatch):
    synthetic_backend(monkeypatch, lambda request: httpx.Response(200, json=response()))
    harness = Harness(database)
    job, _, _ = harness.enqueue()
    runner = worker(database)
    with Session(database[1]) as db:
        item = db.scalar(select(WorkItem.id).where(WorkItem.job_id == UUID(job)))
    assert runner.dispatch(lambda _: pytest.fail("Capture was dispatched")) == 0
    runner.run(item)
    assert runner.inspect(item)["attempts"] == 0 and runner.inspect(item)["status"] == "queued"
    with Session(database[1]) as db:
        assert db.get(CaptureJob, UUID(job)).status == "queued"
        db.delete(db.get(WorkItem, item))
        db.commit()
    runner.backfill()
    with Session(database[1]) as db:
        assert db.scalar(select(WorkItem.id)) is None


def test_provider_failure_retains_explicit_keyword_fallback(database, monkeypatch):
    create(database)
    synthetic_backend(
        monkeypatch, lambda request: httpx.Response(429, content="private diagnostic")
    )
    with TestClient(
        create_app(worker(database).settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    ) as api:
        result = api.post("/v1/retrieval/search", json=query(query="PostgreSQL"))
    assert result.status_code == 200 and result.json()["cards"]
    assert result.json()["degraded"] and "EMBEDDING_UNAVAILABLE" in result.json()["warnings"]
    assert "private diagnostic" not in result.text


def test_forgetting_inside_http_index_response_cannot_resurrect_content(database, monkeypatch):
    target = create(database)

    def handler(request):
        with Session(database[1]) as db:
            MemoryService(db, "developer-a").forget(target.id)
        return httpx.Response(200, json=response())

    synthetic_backend(monkeypatch, handler)
    runner = worker(database)
    assert queue_missing_indexes(runner.sessions, runner.settings) == 1
    process_indexes(database, runner)
    process_indexes(database, worker(database))
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0
        assert db.scalar(select(WorkItem.status)) == "cancelled"


def test_api_configuration_indexes_explicit_saves_without_capture_provider(database, monkeypatch):
    synthetic_backend(monkeypatch, lambda request: httpx.Response(200, json=response()))
    runner = worker(database)
    with TestClient(
        create_app(runner.settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    ) as api:
        created = api.post("/v1/memories", json=payload())
        assert created.status_code == 201
        assert queue_missing_indexes(runner.sessions, runner.settings) == 1
        process_indexes(database, runner)
        result = api.post("/v1/retrieval/search", json=query())
        with Session(database[1]) as db:
            semantic = vector_available(db)
        assert result.status_code == 200 and result.json()["degraded"] is (not semantic)


def test_live_probe_flow_uses_synthetic_http_under_offline_tests(database, monkeypatch):
    from scripts.embedding_probe import BudgetTransport, run

    with Session(database[1]) as db:
        if not vector_available(db):
            # Native Windows still exercises the API/index flow above with explicit fallback.
            pytest.skip(
                "Live-probe ranking needs pgvector; native keyword fallback is tested above"
            )

    def handler(request):
        vectors = []
        for text in json.loads(request.content)["input"]:
            direction = 0 if "primary database" in text or "storage system" in text else 1
            vector = [0.0] * DIMENSIONS
            vector[direction] = 1.0
            vectors.append(vector)
        return httpx.Response(200, json=response(vectors))

    budget = BudgetTransport(20)
    budget.network.close()
    budget.network = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "contextbridge.runtime.CloudflareEmbeddingBackend",
        lambda **options: CloudflareEmbeddingBackend(**options, transport=budget),
    )
    settings = configuration(
        database_url=database[0],
        developer_id="embedding-probe",
        capture_project_id="embedding-probe",
        worker_max_attempts=1,
    )
    report = {"checks": {}}
    run(settings, make_session_factory(database[1]), budget, report)
    assert budget.calls == 10 and not budget.failed
    assert report["checks"]["api_paraphrase_among_three_distractors"]["intended_memory_rank"] == 1
