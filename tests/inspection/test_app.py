"""Real Streamlit widgets driven by AppTest. Skipped where Streamlit is not installed.

Streamlit is not in the project manifest yet, so run these with
``uv run --with streamlit pytest tests/inspection/test_app.py``. The service is a fake HTTP
transport; this checks the screens, not the real API.
"""

from pathlib import Path

import httpx
import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from contextbridge.inspection.client import HttpViewerClient, ViewerSettings  # noqa: E402
from contextbridge.inspection.controller import ViewerController  # noqa: E402
from tests.inspection.fakes import (  # noqa: E402
    PROJECT,
    TOKEN,
    FakeService,
    browse_result,
    inspection,
    memory,
    retrieval_result,
)

APP = str(Path(__file__).resolve().parents[2] / "src" / "contextbridge" / "inspection" / "app.py")


def make_app(service: FakeService) -> AppTest:
    def factory(url, token, project):
        client = HttpViewerClient(ViewerSettings(url, token), project, transport=service.transport)
        return ViewerController(client, session="app-test")

    app = AppTest.from_file(APP, default_timeout=15)
    app.session_state["make_controller"] = factory
    return app


def ready_service(*mems: dict) -> FakeService:
    service = FakeService().on("GET", "/health/ready", body={"status": "ready"})
    service.on("POST", "/v1/inspection/browse", body=browse_result(*mems))
    service.on(
        "GET",
        "/v1/status",
        body={
            "capture_project_id": PROJECT,
            "extraction_configured": True,
            "consolidation_configured": True,
            "embeddings_configured": True,
            "developer_capture_enabled": False,
        },
    )
    service.on("POST", "/v1/inspection/retired", body={"items": [], "next_cursor": None})
    for mem in mems:
        service.on("GET", f"/v1/memories/{mem['id']}", body=inspection(mem))
        service.on(
            "GET",
            f"/v1/memories/{mem['id']}/lifecycle",
            body={"retired_at": None, "current_version": mem["current_version"]},
        )
        service.on(
            "GET",
            f"/v1/memories/{mem['id']}/indexing",
            body={"status": "succeeded", "current_version": mem["current_version"]},
        )
    return service


def signed_in(service: FakeService) -> AppTest:
    app = make_app(service)
    app.run()
    app.sidebar.text_input(key="token").input(TOKEN)
    app.run()
    return app


def texts(app: AppTest) -> list[str]:
    return [element.value for element in app.get("text")]


def messages(app: AppTest, kind: str) -> list[str]:
    return [element.value for element in app.get(kind)]


def button(app: AppTest, key: str):
    return next(b for b in app.button if b.key == key)


def open_first(app: AppTest, mem: dict) -> None:
    button(app, f"browse-open-{mem['id']}").click()
    app.run()


# -- start-up states --------------------------------------------------------------------------


def test_without_a_token_it_asks_for_one_and_calls_nothing():
    service = ready_service(memory())
    app = make_app(service)
    app.run()
    assert not app.exception
    assert any("access token" in m for m in messages(app, "info"))
    assert service.requests == []


def test_invalid_settings_are_explained_without_echoing_them():
    app = make_app(ready_service())
    app.run()
    app.sidebar.text_input(key="url").input("http://user:hunter2@evil.example.com/x")
    app.sidebar.text_input(key="token").input(TOKEN)
    app.run()
    assert any("not valid" in m for m in messages(app, "error"))
    assert "hunter2" not in repr([e.value for e in app.get("error")])


def test_an_unavailable_service_shows_an_error_and_no_screens():
    service = FakeService().on("GET", "/health/ready", status=503, body={"detail": "x"})
    app = signed_in(service)
    assert any("unavailable" in m for m in messages(app, "error"))
    assert len(app.tabs) == 0


def test_a_rejected_token_is_reported():
    service = FakeService().on("GET", "/health/ready", status=401, body={"detail": "x"})
    app = signed_in(service)
    assert any("token" in m for m in messages(app, "error"))


def test_the_token_is_never_displayed_or_requested_by_url():
    service = ready_service(memory())
    app = signed_in(service)
    shown = repr([e.value for e in app.main if hasattr(e, "value")])
    assert TOKEN not in shown
    assert all(TOKEN not in str(r.url) for r in service.requests)


# -- browse and search ------------------------------------------------------------------------


def test_browse_lists_memories_and_marks_disputes():
    mem = memory("uses PostgreSQL")
    service = FakeService().on("GET", "/health/ready", body={"status": "ready"})
    service.on("POST", "/v1/inspection/browse", body=browse_result(mem, decision_state="contested"))
    app = signed_in(service)
    assert "uses PostgreSQL" in texts(app)
    assert any("Disputed" in m for m in messages(app, "warning"))


def test_an_empty_project_says_so():
    app = signed_in(ready_service())
    assert any("Nothing is saved" in m for m in messages(app, "info"))


def test_content_is_shown_as_literal_text_never_as_markup():
    nasty = "<script>alert(1)</script> **bold** [x](http://evil)"
    app = signed_in(ready_service(memory(nasty)))
    assert nasty in texts(app)
    assert all(nasty not in m.value for m in app.markdown)


def test_search_sends_the_selected_project_and_shows_results():
    mem = memory("uses PostgreSQL")
    service = ready_service()
    service.on("POST", "/v1/retrieval/search", body=retrieval_result(mem))
    app = signed_in(service)
    app.text_input(key="search_text").input("database")
    next(b for b in app.button if b.label == "Search").click()
    app.run()
    assert "uses PostgreSQL" in texts(app)
    sent = [
        service.json_of(i) for i, r in enumerate(service.requests) if r.url.path.endswith("search")
    ]
    assert sent and sent[-1]["project_id"] == PROJECT and sent[-1]["query"] == "database"


# -- details, correction, and deletion --------------------------------------------------------


def test_details_show_the_evidence_and_every_version():
    mem = memory("uses PostgreSQL", evidence="Stated in the planning meeting.")
    app = signed_in(ready_service(mem))
    open_first(app, mem)
    assert "Stated in the planning meeting." in texts(app)
    assert any("Version 1" in e.label for e in app.expander)


def test_another_projects_memory_cannot_be_inspected_through_the_view():
    other = memory(project_id="other-project")
    service = ready_service(memory())
    service.on("GET", f"/v1/memories/{other['id']}", body=inspection(other))
    app = signed_in(service)
    app.session_state["selected"] = other["id"]
    app.run()
    assert any("not found" in m for m in messages(app, "warning"))
    assert other["version"]["source"]["evidence"] not in texts(app)


def test_a_correction_is_saved_against_the_version_that_was_opened():
    mem = memory("uses PostgreSQL")
    updated = memory("uses SQLite", number=2, memory_id=mem["id"])
    service = ready_service(mem).on("PUT", f"/v1/memories/{mem['id']}", body=updated)
    app = signed_in(service)
    open_first(app, mem)
    app.text_area(key=f"content-{mem['id']}-1").input("uses SQLite")
    app.text_area(key=f"evidence-{mem['id']}-1").input("Decided in review")
    next(b for b in app.button if b.label == "Save correction").click()
    app.run()
    put = next(i for i, r in enumerate(service.requests) if r.method == "PUT")
    assert service.json_of(put)["expected_version"] == 1
    assert any("Saved as version 2" in m for m in messages(app, "success"))


def test_a_stale_correction_shows_the_newer_version_and_keeps_the_draft():
    mem = memory("uses PostgreSQL", number=1)
    newer = memory("uses MySQL", number=2, memory_id=mem["id"])
    service = ready_service(mem)
    app = signed_in(service)
    open_first(app, mem)
    # A race: the service still shows version 1 when the page loads, but by the time the save
    # arrives someone else has changed it, so the save is rejected and later reads show version 2.
    path = f"/v1/memories/{mem['id']}"
    changed = {"yes": False}

    def reject(_request):
        changed["yes"] = True
        return httpx.Response(409, json={"detail": "changed"})

    def read(_request):
        return httpx.Response(200, json=inspection(newer if changed["yes"] else mem))

    service.on("PUT", path, reject)
    service.on("GET", path, read)
    app.text_area(key=f"content-{mem['id']}-1").input("my edit")
    app.text_area(key=f"evidence-{mem['id']}-1").input("my reason")
    next(b for b in app.button if b.label == "Save correction").click()
    app.run()
    assert any("was not saved" in m for m in messages(app, "warning"))
    assert "uses MySQL" in texts(app)
    assert app.text_area(key=f"content-{mem['id']}-2").value == "my edit"
    assert app.text_area(key=f"evidence-{mem['id']}-2").value == "my reason"
    assert [r.method for r in service.requests].count("PUT") == 1


def test_if_the_memory_moves_on_the_form_is_disabled_until_the_user_reviews_it():
    mem = memory("uses PostgreSQL", number=1)
    newer = memory("uses MySQL", number=2, memory_id=mem["id"])
    service = ready_service(mem)
    app = signed_in(service)
    open_first(app, mem)
    service.on("GET", f"/v1/memories/{mem['id']}", body=inspection(newer))
    app.run()
    assert any("changed after you opened it" in m for m in messages(app, "warning"))
    assert next(b for b in app.button if b.label == "Save correction").disabled
    button(app, "reload").click()
    app.run()
    assert not next(b for b in app.button if b.label == "Save correction").disabled


def test_deleting_needs_the_confirmation_and_then_returns_to_the_list():
    mem = memory()
    service = ready_service(mem).on("DELETE", f"/v1/memories/{mem['id']}", status=204)
    app = signed_in(service)
    open_first(app, mem)
    button(app, "forget").click()
    app.run()
    assert any("Confirm" in m for m in messages(app, "warning"))
    assert "DELETE" not in [r.method for r in service.requests]
    app.checkbox(key=f"confirm-{mem['id']}").check()
    app.run()
    button(app, "forget").click()
    app.run()
    assert "DELETE" in [r.method for r in service.requests]
    assert any("Deleted permanently" in m for m in messages(app, "success"))
    assert app.session_state["selected"] is None


def test_advanced_bundle_import_preserves_original_turn_times():
    import json

    from tests.integration.test_evidence_time import bundle

    value = bundle()
    for event in value["events"]:
        event["project_id"] = PROJECT
    service = ready_service()
    job = "55555555-5555-4555-8555-555555555555"
    service.on(
        "POST",
        "/v2/interactions/bundles",
        status=202,
        body={
            "schema_version": 1,
            "event_id": value["bundle_id"],
            "job_id": job,
            "status": "accepted",
        },
    )
    app = signed_in(service)
    app.text_area(key="import_bundle_json").input(json.dumps(value))
    button(app, "import_bundle").click()
    app.run()
    assert not app.exception
    assert app.session_state["capture_job_id"] == job
    request = next(r for r in service.requests if r.url.path == "/v2/interactions/bundles")
    submitted = json.loads(request.content)
    assert submitted["events"][1]["occurred_at"] == "2026-10-10T10:00:00+05:30"
    assert submitted["events"][1]["source_timezone"] == "Asia/Kolkata"


def test_provenance_control_labels_legacy_evidence():
    mem = memory()
    service = ready_service(mem)
    service.on(
        "POST",
        "/v2/inspection/provenance",
        body={
            "scope": "project",
            "project_id": PROJECT,
            "memory_id": mem["id"],
            "version": 1,
            "metadata": {"schema_version": 1, "precision": "instant"},
        },
    )
    app = signed_in(service)
    open_first(app, mem)
    button(app, f"provenance-{mem['id']}").click()
    app.run()
    assert not app.exception
    assert any("original evidence format" in e.value for e in app.get("caption"))
