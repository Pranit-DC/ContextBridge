import httpx
import pytest

from contextbridge.inspection.client import (
    MESSAGES,
    HttpViewerClient,
    ViewerError,
    ViewerSettings,
)
from tests.inspection.fakes import (
    PROJECT,
    TOKEN,
    URL,
    FakeService,
    browse_result,
    inspection,
    memory,
    update_body,
)


def make_client(service, project=PROJECT):
    return HttpViewerClient(ViewerSettings(URL, TOKEN), project, transport=service.transport)


def get_inspection(service, mem, **kw):
    return service.on("GET", f"/v1/memories/{mem['id']}", body=inspection(mem, **kw))


# -- settings ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000", "http://localhost:9000", "http://[::1]:8000", "http://127.0.0.1"],
)
def test_loopback_origins_are_accepted(url):
    assert ViewerSettings(url, TOKEN).origin.startswith("http://")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:8000",
        "https://example.com",
        "http://user:pass@127.0.0.1:8000",
        "http://127.0.0.1:8000/api",
        "http://127.0.0.1:8000?x=1",
        "http://127.0.0.1:8000#frag",
        "ftp://127.0.0.1",
        "127.0.0.1:8000",
        "http://",
        "http://127.0.0.1:99999",
    ],
)
def test_unsafe_or_malformed_origins_are_rejected_without_echoing_them(url):
    with pytest.raises(ValueError) as raised:
        ViewerSettings(url, TOKEN)
    assert "example.com" not in str(raised.value) and "pass" not in str(raised.value)


def test_remote_services_need_explicit_opt_in_and_https():
    assert ViewerSettings("https://memory.example.com", TOKEN, allow_remote=True)
    with pytest.raises(ValueError):
        ViewerSettings("https://memory.example.com", TOKEN)
    with pytest.raises(ValueError):
        ViewerSettings("http://memory.example.com", TOKEN, allow_remote=True)


def test_a_token_is_required_and_never_shown_in_repr():
    with pytest.raises(ValueError):
        ViewerSettings(URL, "")
    assert TOKEN not in repr(ViewerSettings(URL, TOKEN))


def test_a_project_is_required():
    with pytest.raises(ValueError):
        HttpViewerClient(ViewerSettings(URL, TOKEN), "  ")


# -- transport and error handling -------------------------------------------------------------


def test_requests_carry_the_bearer_token_and_do_not_follow_redirects():
    service = FakeService().on("GET", "/health/ready", body={"status": "ready"})
    make_client(service).status()
    assert service.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"
    redirect = FakeService().on(
        "GET", "/health/ready", lambda r: httpx.Response(302, headers={"location": "http://x/"})
    )
    with pytest.raises(ViewerError) as raised:
        make_client(redirect).status()
    assert raised.value.kind == "unexpected" and len(redirect.requests) == 1


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (401, "unauthorized"),
        (403, "unauthorized"),
        (404, "not_found"),
        (409, "conflict"),
        (422, "invalid"),
        (500, "unavailable"),
        (503, "unavailable"),
        (418, "unexpected"),
    ],
)
def test_http_statuses_map_to_fixed_error_kinds(status, kind):
    service = FakeService().on("GET", "/health/ready", body={"detail": "x"}, status=status)
    with pytest.raises(ViewerError) as raised:
        make_client(service).status()
    assert raised.value.kind == kind and str(raised.value) == MESSAGES[kind]


@pytest.mark.parametrize(
    "detail",
    [
        "bad input SECRET-BODY",
        [{"loc": ["body"], "type": "x", "input": "SECRET-BODY"}],
        {"code": "INVALID_INPUT", "retryable": False, "echo": "SECRET-BODY"},
    ],
)
def test_error_bodies_in_every_documented_format_are_never_copied(detail):
    service = FakeService().on("POST", "/v1/memories/search", body={"detail": detail}, status=422)
    with pytest.raises(ViewerError) as raised:
        make_client(service).search({"scope": "project", "project_id": PROJECT, "query": "q"})
    assert "SECRET-BODY" not in str(raised.value) and raised.value.kind == "invalid"


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("boom"), httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("x")]
)
def test_network_failures_are_reported_as_unavailable_without_details(error):
    def fail(_request):
        raise error

    service = FakeService().on("GET", "/health/ready", fail)
    with pytest.raises(ViewerError) as raised:
        make_client(service).status()
    assert raised.value.kind == "unavailable" and raised.value.__cause__ is None
    assert "boom" not in str(raised.value)


def test_non_json_or_wrongly_shaped_responses_are_unexpected():
    service = FakeService()
    service.on("GET", "/health/ready", lambda r: httpx.Response(200, text="<html>"))
    with pytest.raises(ViewerError) as raised:
        make_client(service).status()
    assert raised.value.kind == "unexpected"
    mem = memory()
    service.on("GET", f"/v1/memories/{mem['id']}", body={"memory": "nope"})
    with pytest.raises(ViewerError) as raised:
        make_client(service).inspect(mem["id"])
    assert raised.value.kind == "unexpected"


def test_status_requires_the_documented_readiness_body():
    service = FakeService().on("GET", "/health/ready", body={"status": "starting"})
    with pytest.raises(ViewerError):
        make_client(service).status()


# -- inspect ----------------------------------------------------------------------------------


def test_inspect_returns_full_evidence_and_history():
    old = memory(number=1, status="SUPERSEDED", valid_to="2026-10-10T00:00:00Z")["version"]
    mem = memory("uses SQLite", number=2, valid_from="2026-10-10T00:00:00Z")
    service = get_inspection(FakeService(), mem, history=[old, mem["version"]])
    result = make_client(service).inspect(mem["id"])
    assert [v["number"] for v in result["history"]] == [1, 2]
    assert result["history"][1]["source"]["evidence"]


def test_a_memory_from_another_project_is_reported_as_not_found():
    other = memory(project_id="other-project")
    with pytest.raises(ViewerError) as raised:
        make_client(get_inspection(FakeService(), other)).inspect(other["id"])
    assert raised.value.kind == "not_found"
    assert "other-project" not in str(raised.value)


def test_developer_global_memories_are_visible_from_any_project():
    mem = memory(scope="developer")
    assert make_client(get_inspection(FakeService(), mem)).inspect(mem["id"])["memory"]["id"]


def test_a_malformed_id_is_rejected_without_any_request():
    service = FakeService()
    with pytest.raises(ViewerError) as raised:
        make_client(service).inspect("../../etc/passwd")
    assert raised.value.kind == "invalid" and service.requests == []


# -- correct ----------------------------------------------------------------------------------


def test_correction_inspects_first_then_sends_the_expected_version():
    mem = memory()
    updated = memory("ContextBridge uses SQLite.", number=2, memory_id=mem["id"])
    service = get_inspection(FakeService(), mem).on(
        "PUT", f"/v1/memories/{mem['id']}", body=updated
    )
    result = make_client(service).correct(mem["id"], update_body(expected_version=1))
    assert service.calls() == [
        ("GET", f"/v1/memories/{mem['id']}"),
        ("PUT", f"/v1/memories/{mem['id']}"),
    ]
    assert service.json_of(1)["expected_version"] == 1
    assert result["current_version"] == 2


def test_a_correction_for_another_projects_memory_never_reaches_the_service():
    other = memory(project_id="other-project")
    service = get_inspection(FakeService(), other)
    with pytest.raises(ViewerError) as raised:
        make_client(service).correct(other["id"], update_body())
    assert raised.value.kind == "not_found"
    assert [m for m, _ in service.calls()] == ["GET"]


def test_a_stale_correction_conflicts_once_and_is_never_retried():
    mem = memory(number=2)
    service = get_inspection(FakeService(), mem).on(
        "PUT", f"/v1/memories/{mem['id']}", body={"detail": "changed"}, status=409
    )
    with pytest.raises(ViewerError) as raised:
        make_client(service).correct(mem["id"], update_body(expected_version=1))
    assert raised.value.kind == "conflict"
    assert [m for m, _ in service.calls()].count("PUT") == 1


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"content": "x"},
        {**update_body(), "expected_version": 0},
        {**update_body(), "content": "   "},
        {**update_body(), "source": {"kind": "agent"}},
        {**update_body(), "unexpected": True},
        None,
    ],
)
def test_invalid_corrections_are_rejected_before_any_request(bad):
    service = FakeService()
    with pytest.raises(ViewerError) as raised:
        make_client(service).correct("33333333-3333-4333-8333-333333333333", bad)
    assert raised.value.kind == "invalid" and service.requests == []


# -- forget -----------------------------------------------------------------------------------


def test_forget_inspects_then_deletes():
    mem = memory()
    service = get_inspection(FakeService(), mem).on(
        "DELETE", f"/v1/memories/{mem['id']}", status=204
    )
    assert make_client(service).forget(mem["id"]) is None
    assert service.calls() == [
        ("GET", f"/v1/memories/{mem['id']}"),
        ("DELETE", f"/v1/memories/{mem['id']}"),
    ]


def test_forget_for_another_projects_memory_never_deletes():
    other = memory(project_id="other-project")
    service = get_inspection(FakeService(), other).on(
        "DELETE", f"/v1/memories/{other['id']}", status=204
    )
    with pytest.raises(ViewerError):
        make_client(service).forget(other["id"])
    assert "DELETE" not in [m for m, _ in service.calls()]


# -- search and browse ------------------------------------------------------------------------

QUERY = {"scope": "project", "project_id": PROJECT, "query": "database", "limit": 2}


def test_search_returns_the_current_endpoint_results_up_to_the_limit():
    mems = [memory(f"m{i}") for i in range(3)]
    service = FakeService().on("POST", "/v1/memories/search", body=mems)
    result = make_client(service).search(QUERY)
    assert len(result["memories"]) == 2
    assert service.json_of(0)["project_id"] == PROJECT


def test_search_cannot_target_a_different_project_than_the_one_selected():
    service = FakeService()
    with pytest.raises(ViewerError) as raised:
        make_client(service).search({**QUERY, "project_id": "other-project"})
    assert raised.value.kind == "invalid" and service.requests == []


@pytest.mark.parametrize(
    "leaked",
    [memory(project_id="other-project"), memory(scope="developer")],
)
def test_search_results_outside_the_selection_are_refused(leaked):
    service = FakeService().on("POST", "/v1/memories/search", body=[leaked])
    with pytest.raises(ViewerError) as raised:
        make_client(service).search(QUERY)
    assert raised.value.kind == "unexpected"


def test_search_includes_developer_memories_only_when_asked():
    dev = memory(scope="developer")
    service = FakeService().on("POST", "/v1/memories/search", body=[dev])
    result = make_client(service).search({**QUERY, "include_developer": True})
    assert len(result["memories"]) == 1


BROWSE = {"schema_version": 1, "scope": "project", "project_id": PROJECT, "limit": 20}


def test_browse_passes_the_cursor_and_returns_the_next_one():
    service = FakeService().on(
        "POST", "/v1/inspection/browse", body=browse_result(memory(), next_cursor="abc")
    )
    result = make_client(service).browse({**BROWSE, "cursor": "prev"})
    assert result["next_cursor"] == "abc" and len(result["items"]) == 1
    assert service.json_of(0)["cursor"] == "prev"


def test_browse_refuses_items_from_another_project():
    service = FakeService().on(
        "POST", "/v1/inspection/browse", body=browse_result(memory(project_id="other-project"))
    )
    with pytest.raises(ViewerError) as raised:
        make_client(service).browse(BROWSE)
    assert raised.value.kind == "unexpected"


def test_browse_cannot_target_a_different_project():
    service = FakeService()
    with pytest.raises(ViewerError):
        make_client(service).browse({**BROWSE, "project_id": "other-project"})
    assert service.requests == []


def test_developer_browse_requires_developer_items():
    dev = memory(scope="developer")
    service = FakeService().on("POST", "/v1/inspection/browse", body=browse_result(dev))
    query = {"schema_version": 1, "scope": "developer", "limit": 20}
    assert len(make_client(service).browse(query)["items"]) == 1
    service.on("POST", "/v1/inspection/browse", body=browse_result(memory()))
    with pytest.raises(ViewerError):
        make_client(service).browse(query)
