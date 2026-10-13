import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from contextbridge.inspection.client import ViewerError
from tests.inspection.fakes import PROJECT, inspection, memory, retrieval_result
from tests.inspection.test_app import button, open_first, ready_service, signed_in, texts
from tests.inspection.test_client import make_client
from tests.inspection.test_controller import controller


def submit(app, label):
    next(b for b in app.button if b.label == label).click()
    app.run()
    assert not app.exception


def test_search_cards_open_without_repeating_hosted_search_and_more_is_bounded():
    mem = memory("Synthetic database policy")
    service = ready_service(mem).on("POST", "/v1/retrieval/search", body=retrieval_result(mem))
    app = signed_in(service)
    app.text_input(key="search_text").input("durable store")
    submit(app, "Search")
    button(app, f"search-open-{mem['id']}").click()
    app.run()
    assert not app.exception and "Synthetic database policy" in texts(app)
    calls = [r for r in service.requests if r.url.path == "/v1/retrieval/search"]
    assert len(calls) == 1 and json.loads(calls[0].content)["limit"] == 3
    next(c for c in app.checkbox if c.label == "More context (up to five memories)").check()
    submit(app, "Search")
    calls = [r for r in service.requests if r.url.path == "/v1/retrieval/search"]
    assert len(calls) == 2 and json.loads(calls[-1].content)["limit"] == 5


def test_save_lost_response_preserves_request_and_source_then_clears_completed_form():
    mem = memory()
    service = ready_service(mem)
    sent = []

    def save(request):
        body = json.loads(request.content)
        sent.append(body)
        if len(sent) == 1:
            return httpx.Response(503, json={"detail": "private response"})
        result = {
            **mem,
            "type": body["type"],
            "conditions": body["conditions"],
            "version": {**mem["version"], "content": body["content"], "source": body["source"]},
        }
        return httpx.Response(201, json=result)

    service.on("POST", "/v1/memories", save)
    app = signed_in(service)
    app.text_area(key="save_text").input("Use synthetic PostgreSQL.")
    app.text_area(key="save_evidence").input("I explicitly confirm PostgreSQL for this project.")
    submit(app, "Save memory")
    submit(app, "Save memory")
    assert len(sent) == 2 and sent[0] == sent[1]
    assert app.text_area(key="save_text").value == ""
    assert app.session_state["selected"] == mem["id"]


def test_import_lost_response_keeps_exact_identity_time_roles_and_shows_pending():
    mem = memory()
    service = ready_service(mem)
    job_id = str(uuid4())
    sent = []

    def imported(request):
        body = json.loads(request.content)
        sent.append(body)
        if len(sent) == 1:
            return httpx.Response(503, json={"detail": "private"})
        return httpx.Response(
            202,
            json={
                "schema_version": 1,
                "status": "accepted",
                "event_id": body["event_id"],
                "job_id": job_id,
            },
        )

    service.on("POST", "/v1/interactions", imported)
    service.on(
        "GET",
        f"/v1/jobs/{job_id}",
        body={
            "schema_version": 1,
            "job_id": job_id,
            "event_id": str(uuid4()),
            "status": "deferred",
            "reason_codes": ["INSUFFICIENT_EVIDENCE"],
            "memory_ids": [],
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    app = signed_in(service)
    messages = [
        {"message_id": "m1", "role": "user", "content": "Use PostgreSQL."},
        {"message_id": "m2", "role": "assistant", "content": "Maybe MySQL?"},
    ]
    app.text_area(key="import_messages").input(json.dumps(messages))
    submit(app, "Import conversation")
    submit(app, "Import conversation")
    assert sent[0] == sent[1] and sent[1]["messages"] == messages
    submit(app, "Check import progress")
    assert any("Pending" in warning.value for warning in app.warning)


def test_retire_restore_require_version_and_fresh_evidence_and_hide_correction():
    mem = memory()
    service = ready_service(mem)
    state = {"retired": False}
    path = f"/v1/memories/{mem['id']}"

    def lifecycle(_):
        return httpx.Response(
            200,
            json={
                "retired_at": datetime.now(UTC).isoformat() if state["retired"] else None,
                "current_version": 1,
            },
        )

    def retired(_):
        state["retired"] = True
        return httpx.Response(
            200,
            json={
                "memory": mem,
                "retired_at": datetime.now(UTC).isoformat(),
                "affected_memories": 1,
            },
        )

    service.on("GET", path + "/lifecycle", lifecycle).on("POST", path + "/retire", retired)
    service.on(
        "POST", path + "/restore", body={"memory": mem, "retired_at": None, "affected_memories": 1}
    )
    app = signed_in(service)
    open_first(app, mem)
    submit(app, "Retire memory")
    assert all(b.label != "Save correction" for b in app.button)
    before = len([r for r in service.requests if r.url.path.endswith("/restore")])
    submit(app, "Restore as a new version")
    assert len([r for r in service.requests if r.url.path.endswith("/restore")]) == before
    app.text_area(key=f"restore-evidence-{mem['id']}").input("I confirm this fact applies again.")
    submit(app, "Restore as a new version")
    body = json.loads(next(r.content for r in service.requests if r.url.path.endswith("/restore")))
    assert body["expected_version"] == body["source_version"] == 1
    assert body["source"]["evidence"] == "I confirm this fact applies again."


def test_connection_change_clears_selection_processing_and_private_drafts():
    mem = memory()
    app = signed_in(ready_service(mem))
    open_first(app, mem)
    app.session_state["capture_job_id"] = str(uuid4())
    app.text_area(key="import_messages").input("private pending draft")
    app.sidebar.text_input(key="project").input("other")
    app.run()
    assert not app.exception and app.session_state.get("selected") is None
    assert "capture_job_id" not in app.session_state
    assert app.text_area(key="import_messages").value == ""


def test_forgetting_clears_import_and_correction_content_from_browser_state():
    mem = memory()
    service = ready_service(mem).on("DELETE", f"/v1/memories/{mem['id']}", status=204)
    app = signed_in(service)
    open_first(app, mem)
    app.text_area(key="import_messages").input("private previously imported statement")
    app.checkbox(key=f"confirm-{mem['id']}").check()
    submit(app, "Delete permanently")
    assert app.text_area(key="import_messages").value == ""
    assert app.session_state.get("selected") is None


@pytest.mark.parametrize("operation", ["retrieve", "retired", "change_lifecycle"])
def test_new_read_and_write_responses_reject_other_project_content(operation):
    mem = memory(project_id="other")
    service = ready_service(mem)
    client = make_client(service)
    with pytest.raises(ViewerError):
        if operation == "retrieve":
            service.on("POST", "/v1/retrieval/search", body=retrieval_result(mem))
            client.retrieve({"scope": "project", "project_id": PROJECT, "query": "database"})
        elif operation == "retired":
            service.on(
                "POST",
                "/v1/inspection/retired",
                body={
                    "items": [{"memory": mem, "retired_at": datetime.now(UTC).isoformat()}],
                    "next_cursor": None,
                },
            )
            client.retired({"scope": "project", "project_id": PROJECT})
        else:
            client.change_lifecycle(
                mem["id"],
                "retire",
                {"scope": "project", "project_id": PROJECT, "expected_version": 1},
            )
    assert not any(r.url.path.endswith("/retire") for r in service.requests)


def test_malformed_import_and_mismatched_inspection_ids_send_no_write():
    mem, other = memory(), memory()
    service = ready_service(mem)
    viewer = controller(service)
    result = viewer.import_conversation(
        str(uuid4()), datetime.now(UTC).isoformat(), '[{"role":"user","role":"tool"}]'
    )
    assert not result.ok and not service.requests
    service.on("GET", f"/v1/memories/{mem['id']}", body=inspection(other))
    with pytest.raises(ViewerError):
        make_client(service).forget(mem["id"])
    assert not any(r.method == "DELETE" for r in service.requests)


def test_degraded_search_keeps_cards_and_explains_limited_service():
    mem = memory()
    service = ready_service(mem).on(
        "POST",
        "/v1/retrieval/search",
        body=retrieval_result(mem, degraded=True, warnings=["SEMANTIC_UNAVAILABLE"]),
    )
    result = controller(service).retrieve("database")
    assert len(result.rows) == 1 and result.notice.level == "warning"
    assert "SEMANTIC_UNAVAILABLE" in result.notice.text


def test_shared_scope_browse_and_retired_listing_are_explicit():
    from tests.inspection.fakes import browse_result

    mem = memory(scope="developer")
    service = ready_service()
    service.on("POST", "/v1/inspection/browse", body=browse_result(mem))
    service.on(
        "POST",
        "/v1/inspection/retired",
        body={
            "items": [{"memory": mem, "retired_at": datetime.now(UTC).isoformat()}],
            "next_cursor": None,
        },
    )
    app = signed_in(service)
    app.selectbox(key="browse_scope").select("Shared across projects")
    app.selectbox(key="retired_scope").select("Shared across projects")
    app.run()
    assert not app.exception and mem["version"]["content"] in texts(app)
    for path in ("/v1/inspection/browse", "/v1/inspection/retired"):
        body = json.loads([r for r in service.requests if r.url.path == path][-1].content)
        assert body["scope"] == "developer" and body["project_id"] is None


def test_explicit_shared_save_does_not_inherit_project_binding():
    mem = memory(scope="developer")
    service = ready_service()

    def save(request):
        body = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                **mem,
                "type": body["type"],
                "version": {**mem["version"], "content": body["content"], "source": body["source"]},
            },
        )

    service.on("POST", "/v1/memories", save)
    result = controller(service).save(
        str(uuid4()), "Use tabs.", "I prefer tabs.", "PREFERENCE", scope="developer"
    )
    assert result.ok
    body = json.loads(service.requests[-1].content)
    assert body["scope"] == "developer" and body["project_id"] is None


def test_user_token_access_statement_save_feedback_persists_and_invalid_save_explains():
    mem = memory("API calls require token access.")
    service = ready_service(mem)

    def save(request):
        body = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                **mem,
                "type": body["type"],
                "conditions": body["conditions"],
                "version": {**mem["version"], "content": body["content"], "source": body["source"]},
            },
        )

    service.on("POST", "/v1/memories", save)
    app = signed_in(service)
    app.text_area(key="save_evidence").input("I confirm that we need token access for API call")
    submit(app, "Save memory")
    assert any("Enter the memory text" in item.value for item in app.warning)
    app.text_area(key="save_text").input("API calls require token access.")
    submit(app, "Save memory")
    assert any("Saved." in item.value for item in app.success)
    app.run()
    assert any("Saved." in item.value for item in app.success)
    assert app.session_state["selected"] == mem["id"]


def test_plain_statement_import_keeps_actual_user_words():
    service = ready_service()
    sent = []

    def accepted(request):
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(
            202,
            json={
                "schema_version": 1,
                "event_id": body["event_id"],
                "job_id": str(uuid4()),
                "status": "accepted",
            },
        )

    service.on("POST", "/v1/interactions", accepted)
    app = signed_in(service)
    app.radio(key="import_format").set_value("My own statement")
    app.text_area(key="import_messages").input("I prefer concise answers in Marathi.")
    submit(app, "Import conversation")
    assert sent[0]["messages"] == [
        {"message_id": "m1", "role": "user", "content": "I prefer concise answers in Marathi."}
    ]
