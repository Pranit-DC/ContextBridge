from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from scripts.v1.budget import BudgetTransport, Ledger


def test_concurrent_clients_share_the_ceiling_and_crash_reservations(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = Ledger(path)
    ledger.reserve("groq")
    requests = []

    def call(_):
        transport = BudgetTransport(
            path,
            "groq",
            transport=httpx.MockTransport(
                lambda r: (requests.append(r), httpx.Response(200, content=b"synthetic"))[1]
            ),
        )
        try:
            return transport.handle_request(httpx.Request("POST", "https://synthetic.invalid"))
        except ModuleError:
            return None

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(call, range(45)))
    assert len(requests) == sum(r is not None for r in results) == 39
    assert Ledger(path).snapshot() == {"calls": {"groq": 40, "cloudflare": 0}, "stopped": True}


@pytest.mark.parametrize("fault", ["quota", "timeout", "oversize"])
def test_first_provider_failure_stops_both_provider_routes_without_retry(tmp_path, fault):
    path, requests = tmp_path / "budget.sqlite", []

    def handler(request):
        requests.append(request)
        if fault == "timeout":
            raise httpx.ReadTimeout("private request detail")
        return httpx.Response(
            429 if fault == "quota" else 200,
            content=b"x" * (2_097_153 if fault == "oversize" else 1),
        )

    transport = BudgetTransport(path, "groq", transport=httpx.MockTransport(handler))
    request = httpx.Request("POST", "https://synthetic.invalid")
    if fault == "quota":
        assert transport.handle_request(request).status_code == 429
    else:
        with pytest.raises(ModuleError):
            transport.handle_request(request)
    with pytest.raises(ModuleError, match="CANCELLED"):
        BudgetTransport(path, "cloudflare", transport=httpx.MockTransport(handler)).handle_request(
            request
        )
    assert len(requests) == 1
    assert Ledger(path).snapshot() == {"calls": {"groq": 1, "cloudflare": 0}, "stopped": True}


def test_configuration_wrapper_preserves_credentials_and_requires_attestation(tmp_path):
    import os
    from unittest.mock import patch

    from scripts.start_v1 import environment
    from tests.retrieval.test_cloudflare import BASE_URL, MODEL_ID, SYNTHETIC_KEY

    path = tmp_path / "synthetic.env"
    text = (
        "CONTEXTBRIDGE_DATABASE_URL=postgresql+psycopg://synthetic/synthetic_test\n"
        "CONTEXTBRIDGE_API_TOKEN=synthetic-token-with-at-least-32-characters\n"
        "CONTEXTBRIDGE_FORMATION_PROVIDER=openai-compatible\n"
        "CONTEXTBRIDGE_FORMATION_MODEL=openai/gpt-oss-120b\n"
        "CONTEXTBRIDGE_FORMATION_BASE_URL=https://api.groq.com/openai/v1\n"
        "CONTEXTBRIDGE_FORMATION_API_KEY=synthetic-only-formation-key\n"
        "CONTEXTBRIDGE_FORMATION_GROQ_FREE_PLAN_CONFIRMED=false\n"
        f"CONTEXTBRIDGE_EMBEDDING_PROVIDER=cloudflare\nCONTEXTBRIDGE_EMBEDDING_API_KEY={SYNTHETIC_KEY}\n"
        f"CONTEXTBRIDGE_EMBEDDING_BASE_URL={BASE_URL}\nCONTEXTBRIDGE_EMBEDDING_MODEL_ID={MODEL_ID}\n"
    )
    path.write_text(text)
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ModuleError, match="INVALID_INPUT"):
            environment(path, project="synthetic")
        env = environment(path, project="synthetic", free_confirmed=True)
    assert env["CONTEXTBRIDGE_FORMATION_ALLOW_PAID"] == "false"
    assert env["CONTEXTBRIDGE_FORMATION_ENABLED"] == "true"
    assert env["CONTEXTBRIDGE_CONSOLIDATION_ENABLED"] == "true"
    assert env["CONTEXTBRIDGE_CAPTURE_PROJECT_ID"] == "synthetic"
    assert path.read_text() == text
