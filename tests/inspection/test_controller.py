import httpx
import pytest

from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
from contextbridge.inspection.controller import UNAVAILABLE, ViewerController
from tests.inspection.fakes import (
    PROJECT,
    TOKEN,
    URL,
    FakeService,
    browse_result,
    inspection,
    memory,
    version,
)


def controller(service):
    client = HttpViewerClient(ViewerSettings(URL, TOKEN), PROJECT, transport=service.transport)
    return ViewerController(client, session="test-session")


def stateful_memory(service, mem, history=None, edges=None):
    service.on("GET", f"/v1/memories/{mem['id']}", body=inspection(mem, history, edges))


# -- status -----------------------------------------------------------------------------------


def test_status_reports_connected_or_a_plain_failure():
    ok = FakeService().on("GET", "/health/ready", body={"status": "ready"})
    assert controller(ok).status().ready is True
    down = FakeService().on("GET", "/health/ready", status=503, body={"detail": "x"})
    result = controller(down).status()
    assert result.ready is False and "unavailable" in result.notice.text


def test_a_rejected_token_is_reported_as_such():
    service = FakeService().on("GET", "/health/ready", status=401, body={"detail": "x"})
    result = controller(service).status()
    assert "token" in result.notice.text and result.notice.level == "error"


# -- search -----------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", None])
def test_an_empty_search_is_not_a_listing_and_sends_nothing(text):
    service = FakeService()
    result = controller(service).search(text)
    assert result.rows == [] and result.notice.level == "info" and service.requests == []


def test_search_shows_rows_and_sends_the_selected_project_and_options():
    service = FakeService().on("POST", "/v1/memories/search", body=[memory("uses PostgreSQL")])
    result = controller(service).search(
        "database", conditions={"environment": "dev"}, include_developer=True, limit=5
    )
    assert [r.text for r in result.rows] == ["uses PostgreSQL"]
    sent = service.json_of(0)
    assert (sent["project_id"], sent["include_developer"], sent["limit"]) == (PROJECT, True, 5)
    assert sent["conditions"] == {"environment": "dev"}


def test_no_match_explains_that_search_is_not_semantic():
    service = FakeService().on("POST", "/v1/memories/search", body=[])
    result = controller(service).search("zzz")
    assert result.rows == [] and "does not guess" in result.notice.text


def test_search_failures_become_a_notice_without_rows():
    service = FakeService().on("POST", "/v1/memories/search", status=503, body={"detail": "x"})
    result = controller(service).search("q")
    assert result.rows == [] and result.notice.level == "error"


def test_a_leaked_result_from_another_project_is_not_displayed():
    leak = memory("secret of another project", project_id="other-project")
    service = FakeService().on("POST", "/v1/memories/search", body=[leak])
    result = controller(service).search("q")
    assert result.rows == [] and "secret of another" not in repr(result)


# -- browse -----------------------------------------------------------------------------------


def test_an_empty_first_page_says_nothing_is_saved():
    service = FakeService().on("POST", "/v1/inspection/browse", body=browse_result())
    result = controller(service).browse()
    assert result.rows == [] and "Nothing is saved" in result.notice.text


def test_browse_pages_forward_with_the_cursor_and_shows_uncertainty():
    service = FakeService().on(
        "POST",
        "/v1/inspection/browse",
        body=browse_result(memory(), next_cursor="next", decision_state="contested"),
    )
    page = controller(service).browse(cursor="current")
    assert page.next_cursor == "next" and page.rows[0].uncertainty.startswith("Disputed")
    assert service.json_of(0)["cursor"] == "current"
    assert service.json_of(0)["project_id"] == PROJECT


def test_an_empty_later_page_is_not_reported_as_an_empty_project():
    service = FakeService().on("POST", "/v1/inspection/browse", body=browse_result())
    assert controller(service).browse(cursor="c").notice is None


def test_browse_can_select_developer_scope_explicitly():
    service = FakeService().on(
        "POST", "/v1/inspection/browse", body=browse_result(memory(scope="developer"))
    )
    result = controller(service).browse(scope="developer")
    assert service.json_of(0)["scope"] == "developer" and len(result.rows) == 1


def test_a_rejected_cursor_is_a_notice_not_a_crash():
    service = FakeService().on("POST", "/v1/inspection/browse", status=422, body={"detail": "x"})
    result = controller(service).browse(cursor="tampered")
    assert result.rows == [] and result.notice.level == "error"


# -- open -------------------------------------------------------------------------------------


def test_open_shows_evidence_and_both_versions():
    old = version("uses PostgreSQL", number=1, status="SUPERSEDED", valid_to="2026-10-10T00:00:00Z")
    mem = memory("uses SQLite", number=2, valid_from="2026-10-10T00:00:00Z")
    service = FakeService()
    stateful_memory(service, mem, history=[old, mem["version"]])
    detail = controller(service).open(mem["id"]).detail
    assert [v.content for v in detail.history] == ["uses SQLite", "uses PostgreSQL"]
    assert all(v.evidence for v in detail.history)


def test_another_projects_memory_cannot_be_opened_and_is_not_named():
    other = memory(project_id="other-project")
    service = FakeService()
    stateful_memory(service, other)
    result = controller(service).open(other["id"])
    assert result.detail is None and result.notice.level == "warning"
    assert "other-project" not in result.notice.text


def test_open_with_a_bad_id_is_a_notice():
    result = controller(FakeService()).open("not-a-uuid")
    assert result.detail is None and result.notice.level == "error"


# -- correct ----------------------------------------------------------------------------------


def test_a_successful_correction_names_the_version_and_reloads_the_history():
    mem = memory(number=1)
    updated = memory("uses SQLite", number=2, memory_id=mem["id"])
    service = FakeService()
    stateful_memory(service, mem)
    service.on("PUT", f"/v1/memories/{mem['id']}", body=updated)
    result = controller(service).correct(mem["id"], 1, "  uses SQLite ", " Told in standup ")
    assert (
        result.ok
        and "version 2" in result.notice.text
        and "earlier version is kept" in result.notice.text
    )
    put = next(i for i, (m, _) in enumerate(service.calls()) if m == "PUT")
    body = service.json_of(put)
    assert body["expected_version"] == 1 and body["content"] == "uses SQLite"
    assert body["source"]["kind"] == "user" and body["source"]["evidence"] == "Told in standup"
    assert (
        body["source"]["agent"] == "contextbridge-viewer"
        and body["source"]["session"] == "test-session"
    )
    assert result.detail is not None


@pytest.mark.parametrize(("content", "evidence"), [("", "why"), ("new", ""), ("  ", "  ")])
def test_a_correction_needs_text_and_a_source_and_sends_nothing_otherwise(content, evidence):
    service = FakeService()
    result = controller(service).correct(
        "33333333-3333-4333-8333-333333333333", 1, content, evidence
    )
    assert not result.ok and result.notice.level == "warning" and service.requests == []


def test_an_overlong_correction_is_refused_locally():
    service = FakeService()
    result = controller(service).correct(
        "33333333-3333-4333-8333-333333333333", 1, "x" * 8001, "why"
    )
    assert not result.ok and service.requests == []


def test_a_stale_correction_reloads_the_newer_version_and_keeps_the_draft_without_retrying():
    newer = memory("uses MySQL", number=3)
    service = FakeService()
    stateful_memory(service, newer)
    service.on("PUT", f"/v1/memories/{newer['id']}", status=409, body={"detail": "changed"})
    result = controller(service).correct(newer["id"], 2, "my edit", "my reason")
    assert not result.ok and result.conflict
    assert result.detail.expected_version == 3 and result.detail.current.content == "uses MySQL"
    assert (result.draft_content, result.draft_evidence) == ("my edit", "my reason")
    assert "was not saved" in result.notice.text
    assert [m for m, _ in service.calls()].count("PUT") == 1
    assert (
        service.json_of(next(i for i, (m, _) in enumerate(service.calls()) if m == "PUT"))[
            "expected_version"
        ]
        == 2
    )


def test_a_correction_for_another_projects_memory_sends_no_change():
    other = memory(project_id="other-project")
    service = FakeService()
    stateful_memory(service, other)
    result = controller(service).correct(other["id"], 1, "edit", "why")
    assert not result.ok and "PUT" not in [m for m, _ in service.calls()]


def test_a_failed_correction_keeps_what_the_user_typed():
    mem = memory()
    service = FakeService()
    stateful_memory(service, mem)
    service.on("PUT", f"/v1/memories/{mem['id']}", status=503, body={"detail": "x"})
    result = controller(service).correct(mem["id"], 1, "edit", "why")
    assert not result.ok and result.draft_content == "edit" and result.draft_evidence == "why"


# -- forget -----------------------------------------------------------------------------------


@pytest.mark.parametrize("confirmed", [False, None, "yes", 1])
def test_forget_without_explicit_confirmation_sends_nothing(confirmed):
    service = FakeService()
    result = controller(service).forget("33333333-3333-4333-8333-333333333333", confirmed)
    assert not result.ok and result.notice.level == "warning" and service.requests == []


def test_a_confirmed_forget_deletes_and_says_it_is_permanent():
    mem = memory()
    service = FakeService().on("DELETE", f"/v1/memories/{mem['id']}", status=204)
    stateful_memory(service, mem)
    result = controller(service).forget(mem["id"], True)
    assert result.ok and "permanently" in result.notice.text
    assert ("DELETE", f"/v1/memories/{mem['id']}") in service.calls()


def test_forget_never_deletes_another_projects_memory():
    other = memory(project_id="other-project")
    service = FakeService().on("DELETE", f"/v1/memories/{other['id']}", status=204)
    stateful_memory(service, other)
    result = controller(service).forget(other["id"], True)
    assert not result.ok and "DELETE" not in [m for m, _ in service.calls()]


def test_a_failed_forget_does_not_claim_success():
    mem = memory()
    service = FakeService().on(
        "DELETE", f"/v1/memories/{mem['id']}", status=503, body={"detail": "x"}
    )
    stateful_memory(service, mem)
    assert controller(service).forget(mem["id"], True).ok is False


# -- unexpected failures ----------------------------------------------------------------------


class Exploding:
    project_id = PROJECT

    def __getattr__(self, name):
        def fail(*_a, **_k):
            raise RuntimeError("token=hunter2 http://internal/db")

        return fail


def test_unexpected_exceptions_become_a_generic_notice_without_their_text():
    ctrl = ViewerController(Exploding())
    results = [
        ctrl.status().notice,
        ctrl.search("q").notice,
        ctrl.browse().notice,
        ctrl.open("x").notice,
        ctrl.correct("x", 1, "a", "b").notice,
        ctrl.forget("x", True).notice,
    ]
    assert all(notice == UNAVAILABLE for notice in results)
    assert "hunter2" not in repr(results)


def test_network_failure_reads_as_unavailable():
    def fail(_request):
        raise httpx.ConnectError("boom")

    service = FakeService().on("POST", "/v1/memories/search", fail)
    assert "unavailable" in controller(service).search("q").notice.text
