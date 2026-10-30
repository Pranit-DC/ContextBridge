"""Widget workflows and recovery; HTTP is synthetic, never an installed service."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from tests.inspection.fakes import inspection, memory, retrieval_result
from tests.inspection.test_app import open_first, ready_service, signed_in, texts
from tests.inspection.test_v1 import submit


def test_first_connection_recovers_from_unavailable_and_rejected_token():
    service = ready_service()
    service.on("GET", "/health/ready", status=503, body={"detail": "synthetic-private"})
    app = signed_in(service)
    assert any("unavailable" in e.value for e in app.error)
    service.on("GET", "/health/ready", status=401, body={"detail": "synthetic-private"})
    app.run()
    assert any("token" in e.value for e in app.error)
    service.on("GET", "/health/ready", body={"status": "ready"})
    app.run()
    assert not app.exception and len(app.tabs) == 5
    assert not any(r.method in ("PUT", "DELETE") for r in service.requests)


def test_empty_search_then_recovery_keeps_query_and_does_not_search_on_rerun():
    mem = memory()
    service = ready_service().on("POST", "/v1/retrieval/search", body=retrieval_result())
    app = signed_in(service)
    app.text_input(key="search_text").input("database")
    submit(app, "Search")
    assert any("No relevant saved memory" in e.value for e in app.info)
    service.on("POST", "/v1/retrieval/search", body=retrieval_result(mem))
    submit(app, "Search")
    assert mem["version"]["content"] in texts(app)
    count = len([r for r in service.requests if r.url.path.endswith("/search")])
    app.run()
    assert len([r for r in service.requests if r.url.path.endswith("/search")]) == count


def test_readiness_outage_preserves_drafts_and_request_ids_until_recovery():
    mem = memory()
    service = ready_service(mem)
    app = signed_in(service)
    open_first(app, mem)
    app.text_area(key="save_text").input("Synthetic save draft")
    app.text_area(key="save_evidence").input("Synthetic save evidence")
    app.text_area(key="import_messages").input("Synthetic import draft")
    app.text_area(key=f"content-{mem['id']}-1").input("Synthetic correction draft")
    app.text_area(key=f"evidence-{mem['id']}-1").input("Synthetic correction evidence")
    app.run()
    assert app.text_area(key="save_text").value == "Synthetic save draft"
    save_id, import_id = app.session_state["save_request_id"], app.session_state["import_event_id"]
    service.on("GET", "/health/ready", status=503, body={"detail": "unavailable"})
    app.run()
    assert len(app.tabs) == 0
    service.on("GET", "/health/ready", body={"status": "ready"})
    app.run()
    assert app.text_area(key="save_text").value == "Synthetic save draft"
    assert app.text_area(key="import_messages").value == "Synthetic import draft"
    assert app.text_area(key=f"content-{mem['id']}-1").value == "Synthetic correction draft"
    assert app.session_state["save_request_id"] == save_id
    assert app.session_state["import_event_id"] == import_id
    assert not any(r.method in ("PUT", "DELETE") for r in service.requests)


def test_reviewing_a_new_version_preserves_unsaved_correction_for_explicit_resubmit():
    mem = memory()
    newer = memory("New service content", number=2, memory_id=mem["id"])
    service = ready_service(mem)
    app = signed_in(service)
    open_first(app, mem)
    app.text_area(key=f"content-{mem['id']}-1").input("My synthetic draft")
    app.text_area(key=f"evidence-{mem['id']}-1").input("My supporting statement")
    app.run()
    service.on("GET", f"/v1/memories/{mem['id']}", body=inspection(newer))
    app.run()
    assert next(b for b in app.button if b.label == "Save correction").disabled
    submit(app, "Review the latest version")
    assert app.text_area(key=f"content-{mem['id']}-2").value == "My synthetic draft"
    assert app.text_area(key=f"evidence-{mem['id']}-2").value == "My supporting statement"
    assert not any(r.method == "PUT" for r in service.requests)


@pytest.mark.parametrize("status", ["failed", "cancelled", "deferred", "succeeded"])
def test_import_terminal_status_never_reimports_and_preserves_user_draft(status):
    job_id, event_id = str(uuid4()), str(uuid4())
    service = ready_service()

    def imported(request):
        body = json.loads(request.content)
        return httpx.Response(
            202,
            json={
                "schema_version": 1,
                "event_id": body["event_id"],
                "job_id": job_id,
                "status": "accepted",
            },
        )

    service.on("POST", "/v1/interactions", imported)
    service.on(
        "GET",
        f"/v1/jobs/{job_id}",
        body={
            "schema_version": 1,
            "job_id": job_id,
            "event_id": event_id,
            "status": status,
            "reason_codes": [],
            "memory_ids": [],
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    app = signed_in(service)
    draft = '[{"message_id":"m1","role":"user","content":"Use synthetic PostgreSQL."}]'
    app.text_area(key="import_messages").input(draft)
    submit(app, "Import conversation")
    submit(app, "Check import progress")
    assert f"Processing: {status}" in texts(app)
    app.run()
    assert app.text_area(key="import_messages").value == draft
    assert len([r for r in service.requests if r.url.path == "/v1/interactions"]) == 1


def test_malformed_import_sends_nothing_and_corrected_draft_can_be_submitted():
    service = ready_service()
    app = signed_in(service)
    app.text_area(key="import_messages").input("invalid json")
    submit(app, "Import conversation")
    assert app.text_area(key="import_messages").value == "invalid json"
    assert not any(r.url.path == "/v1/interactions" for r in service.requests)
    # A failed network response also preserves the identity/draft for an explicit retry.
    service.on("POST", "/v1/interactions", status=503, body={"detail": "synthetic-private"})
    app.text_area(key="import_messages").input(
        '[{"message_id":"m1","role":"user","content":"Use PostgreSQL."}]'
    )
    submit(app, "Import conversation")
    identifier = app.session_state["import_event_id"]
    submit(app, "Import conversation")
    calls = [r for r in service.requests if r.url.path == "/v1/interactions"]
    assert len(calls) == 2 and json.loads(calls[0].content) == json.loads(calls[1].content)
    assert app.session_state["import_event_id"] == identifier


@pytest.mark.parametrize(
    "status", ["queued", "running", "succeeded", "failed", "deferred", "cancelled"]
)
def test_consolidation_queue_and_status_are_explicit_and_never_resubmit(status):
    service = ready_service()
    job_id = str(uuid4())
    service.on(
        "POST", "/v1/consolidations", body={"status": "queued", "job_id": job_id, "source_count": 2}
    )
    service.on(
        "GET",
        f"/v1/consolidations/{job_id}",
        body={
            "job_id": job_id,
            "status": status,
            "reason_codes": [],
            "memory_ids": [],
        },
    )
    app = signed_in(service)
    submit(app, "Queue consolidation")
    submit(app, "Check consolidation progress")
    assert f"Consolidation: {status}" in texts(app)
    app.run()
    assert len([r for r in service.requests if r.url.path == "/v1/consolidations"]) == 1


def test_retirement_version_conflict_requires_review_and_does_not_retry():
    mem = memory()
    service = ready_service(mem).on("POST", f"/v1/memories/{mem['id']}/retire", status=409)
    app = signed_in(service)
    open_first(app, mem)
    submit(app, "Retire memory")
    assert any("changed" in w.value for w in app.warning)
    app.run()
    assert len([r for r in service.requests if r.url.path.endswith("/retire")]) == 1
