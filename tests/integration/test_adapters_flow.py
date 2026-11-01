"""Actual merged modules/API/DB, with synthetic recorded model outputs, not a quality report."""

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from mcp import Client
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.background.maintenance import dispatch_cycle
from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import load_providers
from contextbridge.capture_adapters.transcript import TranscriptClient
from contextbridge.config import Settings
from contextbridge.db import make_session_factory
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.inspection.client import HttpViewerClient, ViewerError, ViewerSettings
from contextbridge.mcp_adapter.config import MCPSettings
from contextbridge.mcp_adapter.gateway import MemoryGateway
from contextbridge.mcp_adapter.server import create_server
from contextbridge.models import EmbeddingModel, Memory, MemoryEmbedding, ReindexJob, WorkItem
from contextbridge.persistence.vectors import vector_available
from tests.conftest import TEST_TOKEN
from tests.engine.fakes import fixture
from tests.integration.retrieval_fakes import create
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def configuration(database, **changes):
    return Settings(
        _env_file=None,
        database_url=database[0],
        api_token=TEST_TOKEN,
        developer_id="developer-a",
        capture_project_id="contextbridge",
        integration_factory="tests.integration.provider_factory:make",
        embedding_model_id="recorded-integration-v1",
        embedding_dimensions=2,
        **changes,
    )


def index_work(database, worker):
    with Session(database[1]) as db:
        items = list(db.scalars(select(WorkItem.id).where(WorkItem.kind == "reindex")))
    for item in items:
        worker.run(item)


def test_transcript_to_actual_modules_viewer_fresh_mcp_correction_and_forget(database):
    settings = configuration(database)
    sessions = make_session_factory(database[1])
    providers = load_providers(settings, sessions)
    worker = WorkRunner(sessions, settings, providers)
    event = fixture("captured-event")
    event["event_id"] = str(uuid4())
    event["messages"] = [
        {"message_id": "message-1", "role": "user", "content": "Use PostgreSQL database."}
    ]
    adapter_settings = MCPSettings(_env_file=None, api_token=TEST_TOKEN, project_id="contextbridge")
    with TestClient(create_app(settings)) as api:

        def forward(request):
            response = api.request(
                request.method, request.url.path, content=request.content, headers=request.headers
            )
            return httpx.Response(
                response.status_code, content=response.content, headers=response.headers
            )

        transport = httpx.MockTransport(forward)
        importer = TranscriptClient(adapter_settings, transport=transport)
        accepted = importer.submit(event)
        assert importer.submit(event).job_id == accepted.job_id
        with Session(database[1]) as db:
            item = db.scalar(select(WorkItem.id).where(WorkItem.job_id == accepted.job_id))
        worker.run(item)
        assert importer.status(accepted.job_id).status == "succeeded"
        memory_id = importer.status(accepted.job_id).memory_ids[0]
        assert queue_missing_indexes(sessions, settings) == 1
        assert queue_missing_indexes(sessions, settings) == 0
        index_work(database, worker)
        viewer = HttpViewerClient(ViewerSettings(token=TEST_TOKEN), "contextbridge", transport)
        inspected = viewer.inspect(memory_id)
        assert inspected["history"][0]["source"]["evidence"] == "Use PostgreSQL database."

        async def cross_agent():
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

            with Session(database[1]) as db:
                semantic = vector_available(db)
            async with agent("codex") as codex:
                # This text has no lexical match; only the recorded semantic fixture supplies it.
                query = "persistent server" if semantic else "PostgreSQL"
                result = await codex.call_tool("memory_retrieve", {"query": query})
                assert not result.is_error
                assert result.structured_content["cards"][0]["memory_id"] == str(memory_id)
                assert result.structured_content["degraded"] is (not semantic)
                changed = await codex.call_tool(
                    "memory_update",
                    {
                        "memory_id": str(memory_id),
                        "expected_version": 1,
                        "content": "Use SQLite database.",
                        "source": {
                            "kind": "user",
                            "interaction": "turn-2",
                            "evidence": "Use SQLite database.",
                        },
                    },
                )
                assert not changed.is_error
            assert queue_missing_indexes(sessions, settings) == 1
            index_work(database, worker)
            # A fresh MCP session sees the correction, preserving the old explicit interface.
            async with agent("claude-code") as claude:
                fresh = await claude.call_tool("memory_retrieve", {"query": "SQLite"})
                assert fresh.structured_content["cards"][0]["version_number"] == 2
                legacy = await claude.call_tool("memory_search", {"query": "SQLite"})
                assert legacy.structured_content["memories"][0]["current_version"] == 2

        asyncio.run(cross_agent())
        assert len(viewer.inspect(memory_id)["history"]) == 2
        viewer.forget(memory_id)
        with pytest.raises(ViewerError):
            viewer.inspect(memory_id)
        with pytest.raises(ModuleError, match="VERSION_CONFLICT"):
            importer.submit(event)
        worker.run(item)
        assert queue_missing_indexes(sessions, settings) == 0
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 0
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0


def test_index_sweep_is_scoped_recoverable_and_model_change_requeues(database):
    settings = configuration(database)
    sessions = make_session_factory(database[1])
    target = create(database)
    create(database, project_id="other-project")
    create(database, owner="developer-b")
    create(database, scope="developer", project_id=None)
    assert queue_missing_indexes(sessions, settings) == 1
    with Session(database[1]) as db:
        job = db.scalar(select(ReindexJob))
        assert job.project_id == "contextbridge" and job.developer_id == "developer-a"
    # Restarted assembly recovers from the persisted version/job, without interpretation replay.
    worker = WorkRunner(sessions, settings, load_providers(settings, sessions))
    index_work(database, worker)
    assert queue_missing_indexes(sessions, settings) == 0
    newer = settings.model_copy(update={"embedding_model_id": "recorded-integration-v2"})
    assert queue_missing_indexes(sessions, newer) == 1
    index_work(database, WorkRunner(sessions, newer, load_providers(newer, sessions)))
    with Session(database[1]) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(MemoryEmbedding)
                .where(MemoryEmbedding.version_id == target.version.id)
            )
            == 2
        )


def test_invalid_index_configuration_does_not_block_capture_dispatch(database, caplog):
    settings = configuration(database).model_copy(update={"embedding_dimensions": 3})
    sessions = make_session_factory(database[1])
    create(database)
    with sessions() as db:
        db.add(
            EmbeddingModel(
                developer_id="developer-a", model_id=settings.embedding_model_id, dimensions=2
            )
        )
        db.commit()
    harness = Harness(database)
    job, _, _ = harness.enqueue("Use PostgreSQL database.")
    worker = WorkRunner(sessions, settings, load_providers(settings, sessions))
    delivered = []
    assert dispatch_cycle(worker, delivered.append) == 1
    assert "index_discovery_unavailable reason=INVALID_INPUT" in caplog.text
    for item in delivered:
        worker.run(item)
    with sessions() as db:
        item = db.scalar(select(WorkItem.id).where(WorkItem.job_id == UUID(job)))
    assert worker.inspect(item)["status"] == "succeeded"
