import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import WorkerProviders, load_providers
from contextbridge.db import make_session_factory
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.engine.modules import ModuleGateway
from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
from contextbridge.inspection.controller import ViewerController
from contextbridge.models import CaptureEvent, Memory, MemoryEmbedding, WorkItem
from tests.background.test_consolidation import Proposals
from tests.background.test_work import work_id
from tests.conftest import TEST_TOKEN
from tests.integration.test_adapters_flow import configuration, index_work

pytestmark = pytest.mark.integration


def test_viewer_shared_api_workers_history_consolidation_lifecycle_and_forget(database):
    settings = configuration(database)
    sessions = make_session_factory(database[1])
    worker = WorkRunner(sessions, settings, load_providers(settings, sessions))
    with TestClient(create_app(settings)) as api:

        def forward(request):
            response = api.request(
                request.method, request.url.path, content=request.content, headers=request.headers
            )
            return httpx.Response(
                response.status_code, content=response.content, headers=response.headers
            )

        viewer = ViewerController(
            HttpViewerClient(
                ViewerSettings(token=TEST_TOKEN), "contextbridge", httpx.MockTransport(forward)
            ),
            session="v1-test",
        )
        assert viewer.status().ready
        saved = viewer.save(str(uuid4()), "Keep daily backups.", "Keep daily backups.", "FACT")
        assert (
            saved.ok
            and viewer.action("indexing", saved.data["id"]).data["status"] == "awaiting_worker"
        )
        accepted = viewer.import_conversation(
            str(uuid4()),
            datetime.now(UTC).isoformat(),
            json.dumps(
                [{"message_id": "m1", "role": "user", "content": "Use PostgreSQL database."}]
            ),
        )
        assert accepted.ok
        item = work_id(database, accepted.data["job_id"])
        worker.run(item)
        # Fresh execution replays the durable result rather than re-extracting.
        WorkRunner(sessions, settings, load_providers(settings, sessions)).run(item)
        progress = viewer.action("processing", accepted.data["job_id"])
        assert progress.ok and progress.data["status"] == "succeeded"
        memory_id = progress.data["memory_ids"][0]
        assert queue_missing_indexes(sessions, settings) == 2
        assert viewer.action("indexing", memory_id).data["status"] == "queued"
        index_work(database, worker)
        assert viewer.action("indexing", memory_id).data["status"] == "succeeded"
        found = viewer.retrieve("PostgreSQL")
        assert memory_id in [r.memory_id for r in found.rows]
        assert viewer.correct(
            memory_id,
            1,
            "Use PostgreSQL with daily backups.",
            "We explicitly selected PostgreSQL with daily backups.",
        ).ok
        assert len(viewer.open(memory_id).detail.history) == 2
        assert viewer.action("indexing", memory_id).data["status"] == "awaiting_worker"
        assert queue_missing_indexes(sessions, settings) == 1
        index_work(database, worker)
        api.app.state.modules = ModuleGateway(consolidator=Proposals())
        queued = viewer.action("consolidate", {"scope": "project", "project_id": "contextbridge"})
        assert queued.ok and queued.data["source_count"] == 2
        consolidator = WorkRunner(
            sessions, settings, WorkerProviders(ModuleGateway(consolidator=Proposals()))
        )
        consolidator.run(work_id(database, queued.data["job_id"]))
        consolidated = viewer.action("consolidation_status", queued.data["job_id"])
        assert consolidated.ok and consolidated.data["status"] == "succeeded"
        summary_id = consolidated.data["memory_ids"][0]
        sources = viewer.action("sources", summary_id)
        assert sources.ok and len(sources.data) == 2
        assert {row["memory"]["id"] for row in sources.data} == {memory_id, saved.data["id"]}
        retired = viewer.change_lifecycle(memory_id, "retire", 2)
        assert retired.ok and retired.data["affected_memories"] == 2
        assert viewer.action("indexing", memory_id).data["status"] == "retired"
        assert {r.memory_id for r in viewer.retired().rows} == {memory_id, summary_id}
        assert memory_id not in [r.memory_id for r in viewer.retrieve("PostgreSQL").rows]
        restored = viewer.change_lifecycle(
            memory_id,
            "restore",
            2,
            source_version=2,
            evidence="I confirm PostgreSQL still applies.",
        )
        assert restored.ok and restored.data["memory"]["current_version"] == 3
        assert len(viewer.open(memory_id).detail.history) == 3
        assert not viewer.change_lifecycle(
            summary_id, "restore", 1, source_version=1, evidence="Restore this summary."
        ).ok
        assert queue_missing_indexes(sessions, settings) == 1
        index_work(database, worker)
        assert viewer.forget(memory_id, True).ok
        assert not viewer.open(summary_id).detail
        worker.run(item)  # cancelled import cannot resurrect forgotten memory
        assert viewer.forget(saved.data["id"], True).ok
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 0
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0
        assert all(event.payload is None for event in db.scalars(select(CaptureEvent)))
        assert (
            db.scalar(
                select(WorkItem).where(WorkItem.job_id == UUID(accepted.data["job_id"]))
            ).status
            == "cancelled"
        )


def test_indexing_status_does_not_expose_other_developer_memory(client, clients):
    from tests.test_validation import payload

    memory_id = client.post("/v1/memories", json=payload()).json()["id"]
    assert client.get(f"/v1/memories/{memory_id}/indexing").json()["status"] == "not_configured"
    assert clients("other").get(f"/v1/memories/{memory_id}/indexing").status_code == 404


def test_shared_indexing_requires_explicit_binding_and_reports_actual_vector(database):
    from tests.test_validation import payload

    settings = configuration(database)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"}) as api:
        saved = api.post("/v1/memories", json=payload(scope="developer", project_id=None)).json()
        assert api.get(f"/v1/memories/{saved['id']}/indexing").json()["status"] == "not_configured"
    enabled = settings.model_copy(update={"capture_allow_developer": True})
    sessions = make_session_factory(database[1])
    assert queue_missing_indexes(sessions, enabled) == 1
    index_work(database, WorkRunner(sessions, enabled, load_providers(enabled, sessions)))
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"}) as api:
        assert api.get(f"/v1/memories/{saved['id']}/indexing").json()["status"] == "succeeded"
