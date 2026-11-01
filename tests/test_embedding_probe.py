import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from scripts.embedding_probe import BudgetTransport, ProbeFailure, safe_database


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://localhost/project",
        "postgresql+psycopg://example.com/project_test",
        "sqlite:///project_test",
    ],
)
def test_probe_refuses_non_test_or_remote_databases(url):
    with pytest.raises(ProbeFailure):
        safe_database(url)


def test_probe_budget_stops_after_failure_and_never_retries():
    budget = BudgetTransport(20)
    budget.network.close()
    budget.network = httpx.MockTransport(lambda request: httpx.Response(429))
    request = httpx.Request("POST", "https://example.com")
    assert budget.handle_request(request).status_code == 429
    with pytest.raises(ModuleError):
        budget.handle_request(request)
    assert budget.calls == 1 and budget.failed


def test_probe_budget_never_exceeds_limit():
    budget = BudgetTransport(2)
    budget.network.close()
    budget.network = httpx.MockTransport(lambda request: httpx.Response(200))
    request = httpx.Request("POST", "https://example.com")
    budget.handle_request(request)
    budget.handle_request(request)
    with pytest.raises(ModuleError):
        budget.handle_request(request)
    assert budget.calls == 2
