import httpx
import pytest

from scripts.run_v1_linux import wait_for_service


@pytest.mark.parametrize(
    "status,expected",
    [
        (
            {
                "capture_project_id": "another-project",
                "extraction_configured": True,
                "embeddings_configured": True,
            },
            "different project",
        ),
        (
            {
                "capture_project_id": "linux-test",
                "extraction_configured": False,
                "embeddings_configured": True,
            },
            "not configured",
        ),
        ([], "invalid configuration"),
        (
            {
                "capture_project_id": "linux-test",
                "extraction_configured": True,
                "embeddings_configured": True,
            },
            None,
        ),
    ],
)
def test_launcher_checks_exact_runtime_binding_and_capabilities_without_models(status, expected):
    paths = []

    def handle(request):
        paths.append(request.url.path)
        assert request.headers["Authorization"] == "Bearer synthetic-token"
        return httpx.Response(
            200, json={"status": "ready"} if request.url.path == "/health/ready" else status
        )

    result = wait_for_service("synthetic-token", "linux-test", client=httpx.MockTransport(handle))
    assert result is None if expected is None else expected in result
    assert paths == ["/health/ready", "/v1/status"]


def test_launcher_authentication_failure_stops_without_repeated_requests():
    paths = []

    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(401, json={"detail": "never expose response body"})

    result = wait_for_service("synthetic-token", "linux-test", client=httpx.MockTransport(handle))
    assert "access token" in result
    assert "never expose" not in result
    assert paths == ["/health/ready"]
