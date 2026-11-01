from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from contextbridge.inspection.client import HttpViewerClient, ViewerSettings  # noqa: E402
from contextbridge.inspection.controller import ViewerController  # noqa: E402
from contextbridge.local_ui.settings import SettingsStore  # noqa: E402
from tests.inspection.fakes import memory  # noqa: E402
from tests.inspection.test_app import ready_service  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src/contextbridge/local_ui/app.py"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        "CONTEXTBRIDGE_API_TOKEN='synthetic-ui-access-token-1234567890'\n"
        "CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://test:test@127.0.0.1/ui_test'\n"
    )
    monkeypatch.setenv("CONTEXTBRIDGE_LOCAL_ENV_FILE", str(path))
    monkeypatch.delenv("CONTEXTBRIDGE_LOCAL_ALLOW_RESTART", raising=False)
    service = ready_service(memory())

    def factory(url, token, project):
        return ViewerController(
            HttpViewerClient(ViewerSettings(url, token), project, transport=service.transport)
        )

    app = AppTest.from_file(str(APP), default_timeout=15)
    app.session_state["make_controller"] = factory
    app.run()
    assert not app.exception
    return app, SettingsStore(path), service


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_workspace_navigation_loads_only_selected_memory_task(workspace):
    app, _, service = workspace
    assert any("PostgreSQL" in element.value for element in app.text)
    service.requests.clear()
    app.sidebar.radio(key="workspace_page").set_value("Add memory").run()
    assert not app.exception
    assert any(b.label == "Save memory" for b in app.button)
    assert all(request.url.path != "/v1/inspection/browse" for request in service.requests)
    app.sidebar.radio(key="workspace_page").set_value("Activity").run()
    assert not app.exception


def test_settings_work_without_service_and_make_no_provider_calls(workspace):
    app, store, service = workspace
    service.requests.clear()
    app.sidebar.radio(key="workspace_page").set_value("Settings").run()
    assert not app.exception and service.requests == []
    assert app.text_input(key="cfg_groq_secret").value == ""
    assert button(app, "Test Groq").disabled
    assert button(app, "Apply settings to services").disabled
    before = store.path.read_bytes()
    app.text_input(key="cfg_groq_secret").input("synthetic-private-groq-key-12345")
    app.checkbox(key="cfg_free").check()
    app.toggle(key="cfg_processing").set_value(True)
    button(app, "Save settings").click().run()
    assert not app.exception
    assert store.path.read_bytes() != before and store.snapshot().preferences.processing
    assert app.text_input(key="cfg_groq_secret").value == ""
    assert any("saved locally" in s.value for s in app.success)
    assert service.requests == []


def test_setup_opens_settings_before_any_service_or_provider_request(workspace, monkeypatch):
    previous, _, service = workspace
    service.requests.clear()
    monkeypatch.setenv("CONTEXTBRIDGE_LOCAL_START_SETTINGS", "true")
    app = AppTest.from_file(str(APP), default_timeout=15)
    app.session_state["make_controller"] = previous.session_state["make_controller"]
    app.run()
    assert not app.exception
    assert app.sidebar.radio(key="workspace_page").value == "Settings"
    assert service.requests == []


def test_invalid_key_is_cleared_and_stale_edits_are_rejected(workspace):
    app, store, _ = workspace
    app.sidebar.radio(key="workspace_page").set_value("Settings").run()
    before = store.path.read_bytes()
    app.text_input(key="cfg_groq_secret").input("invalid key with spaces")
    button(app, "Save settings").click().run()
    assert not app.exception and store.path.read_bytes() == before
    assert app.text_input(key="cfg_groq_secret").value == ""
    assert app.warning
    store.save(
        store.snapshot().revision,
        store.snapshot().preferences.model_copy(update={"grouping": True}),
    )
    app.run()
    assert not app.exception and button(app, "Save settings").disabled
    assert any("another window" in s.value for s in app.warning)
    button(app, "Reload saved settings").click().run()
    assert not app.exception and not button(app, "Save settings").disabled


def test_workspace_keeps_save_and_bundle_drafts_across_navigation_outage_and_settings(workspace):
    app, _, service = workspace
    app.sidebar.radio(key="workspace_page").set_value("Add memory").run()
    app.text_area(key="save_text").input("Unsaved project fact").run()
    app.text_area(key="save_evidence").input("Original supporting statement").run()
    save_id = app.session_state["save_request_id"]
    app.segmented_control(key="workspace_add").set_value("Import conversation").run()
    app.text_area(key="import_bundle_json").input('{"synthetic": "unfinished bundle"}').run()
    bundle = app.text_area(key="import_bundle_json").value
    app.text_area(key="import_messages").input("Unsaved conversation").run()
    import_id = app.session_state["import_event_id"]
    app.sidebar.radio(key="workspace_page").set_value("Settings").run()
    app.sidebar.radio(key="workspace_page").set_value("Add memory").run()
    assert app.text_area(key="import_bundle_json").value == bundle
    service.on("GET", "/health/ready", status=503)
    app.run()
    service.on("GET", "/health/ready", body={"status": "ready"})
    app.run()
    assert not app.exception
    assert app.text_area(key="import_bundle_json").value == bundle
    assert app.text_area(key="import_messages").value == "Unsaved conversation"
    assert app.session_state["import_event_id"] == import_id
    app.segmented_control(key="workspace_add").set_value("Save a memory").run()
    assert app.text_area(key="save_text").value == "Unsaved project fact"
    assert app.text_area(key="save_evidence").value == "Original supporting statement"
    assert app.session_state["save_request_id"] == save_id
    assert not any(
        r.method in ("PUT", "DELETE") or r.url.path == "/v2/interactions/bundles"
        for r in service.requests
    )


def test_workspace_connection_change_clears_drafts_and_pending_merge(workspace):
    app, _, _ = workspace
    app.sidebar.radio(key="workspace_page").set_value("Add memory").run()
    app.text_area(key="save_text").input("Private draft in first project").run()
    app.session_state["compact_preview"] = ("old", {"verification_token": "old-token"})
    app.sidebar.text_input(key="workspace_project").input("new-project").run()
    assert "compact_preview" not in app.session_state
    assert app.text_area(key="save_text").value == ""
