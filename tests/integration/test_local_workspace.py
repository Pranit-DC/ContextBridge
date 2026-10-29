"""Actual workspace widgets → HTTP client → real API → dedicated PostgreSQL."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from contextbridge.api import create_app  # noqa: E402
from contextbridge.config import Settings  # noqa: E402
from contextbridge.engine.modules import ModuleGateway  # noqa: E402
from contextbridge.inspection.client import HttpViewerClient, ViewerSettings  # noqa: E402
from contextbridge.inspection.controller import ViewerController  # noqa: E402
from contextbridge.models import Memory, MemoryVersion  # noqa: E402
from contextbridge.retrieval import Retriever  # noqa: E402
from tests.conftest import TEST_TOKEN  # noqa: E402

pytestmark = pytest.mark.integration
APP = Path(__file__).resolve().parents[2] / "src/contextbridge/local_ui/app.py"


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_workspace_save_inspect_correct_retire_restore_and_forget(database, tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        f"CONTEXTBRIDGE_DATABASE_URL='{database[0]}'\nCONTEXTBRIDGE_API_TOKEN='{TEST_TOKEN}'\n"
    )
    monkeypatch.setenv("CONTEXTBRIDGE_LOCAL_ENV_FILE", str(path))
    monkeypatch.delenv("CONTEXTBRIDGE_API_URL", raising=False)
    settings = Settings(
        _env_file=None,
        database_url=database[0],
        api_token=TEST_TOKEN,
        developer_id="workspace-integration",
    )
    with TestClient(create_app(settings, modules=ModuleGateway(retriever=Retriever()))) as api:
        responses = []

        def handle(request):
            result = api.request(
                request.method,
                request.url.path,
                headers={"Authorization": request.headers["Authorization"]},
                json=json.loads(request.content) if request.content else None,
            )
            responses.append((request.method, request.url.path, result.status_code))
            return httpx.Response(
                result.status_code,
                content=result.content,
                headers={"content-type": "application/json"},
            )

        def factory(url, token, project):
            return ViewerController(
                HttpViewerClient(
                    ViewerSettings(url, token), project, transport=httpx.MockTransport(handle)
                )
            )

        app = AppTest.from_file(str(APP), default_timeout=15)
        app.session_state["make_controller"] = factory
        app.run()
        assert not app.exception
        app.sidebar.radio(key="workspace_page").set_value("Add memory").run()
        app.text_area(key="save_text").input("The project database uses PostgreSQL.")
        app.text_area(key="save_evidence").input("Use PostgreSQL for this project database.")
        button(app, "Save memory").click().run()
        assert not app.exception
        assert not app.error and not app.warning, (
            [item.value for item in app.error],
            [item.value for item in app.warning],
            responses,
        )
        with Session(database[1]) as session:
            saved = session.scalar(select(Memory))
            assert saved.current_version == 1
            memory_id = saved.id
        assert any("Use PostgreSQL" in t.value for t in app.text)
        app.text_area(key=f"content-{memory_id}-1").input("The project database uses SQLite.")
        app.text_area(key=f"evidence-{memory_id}-1").input(
            "Correction: use SQLite instead of PostgreSQL."
        )
        button(app, "Save correction").click().run()
        assert not app.exception
        with Session(database[1]) as session:
            assert session.get(Memory, memory_id).current_version == 2
            assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 2
        button(app, "Retire memory").click().run()
        assert not app.exception
        with Session(database[1]) as session:
            assert session.get(Memory, memory_id).retired_at is not None
        app.selectbox(key=f"restore-version-{memory_id}").set_value(2)
        app.text_area(key=f"restore-evidence-{memory_id}").input(
            "SQLite remains the confirmed database."
        )
        button(app, "Restore as a new version").click().run()
        assert not app.exception
        with Session(database[1]) as session:
            assert session.get(Memory, memory_id).retired_at is None
            assert session.get(Memory, memory_id).current_version == 3
        app.checkbox(key=f"confirm-{memory_id}").check()
        button(app, "Delete permanently").click().run()
        assert not app.exception
        with Session(database[1]) as session:
            assert session.scalar(select(func.count()).select_from(Memory)) == 0
            assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 0
