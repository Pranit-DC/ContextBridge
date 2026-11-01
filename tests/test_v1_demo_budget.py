from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from scripts.v1.budget import BudgetTransport, Ledger


def test_concurrent_ledger_initialization_and_stopped_state_are_shared(tmp_path):
    from scripts.v1.budget import exclusive

    path = tmp_path / "shared.sqlite"

    def reserve(_):
        ledger = Ledger(path)
        with exclusive(path):
            ledger.reserve("groq")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(reserve, range(32)))
    ledger = Ledger(path)
    assert ledger.snapshot() == {"calls": {"groq": 32, "cloudflare": 0}, "stopped": False}
    ledger.stop()
    with pytest.raises(ModuleError, match="CANCELLED"):
        Ledger(path).reserve("cloudflare")
    assert Ledger(path).snapshot()["calls"] == {"groq": 32, "cloudflare": 0}


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


def test_lower_authorized_ceiling_survives_new_clients_and_cannot_be_raised(tmp_path):
    path = tmp_path / "capped.sqlite"
    Ledger(path, limits={"groq": 2, "cloudflare": 1})
    Ledger(path, limits={"groq": 10, "cloudflare": 10})
    requests = []

    def send(request):
        requests.append(request)
        return httpx.Response(200, content=b"synthetic")

    for _ in range(2):
        BudgetTransport(path, "groq", transport=httpx.MockTransport(send)).handle_request(
            httpx.Request("POST", "https://synthetic.invalid")
        )
    with pytest.raises(ModuleError, match="CANCELLED"):
        BudgetTransport(path, "groq", transport=httpx.MockTransport(send)).handle_request(
            httpx.Request("POST", "https://synthetic.invalid")
        )
    assert len(requests) == 2
    assert Ledger(path).snapshot()["stopped"]
    assert Ledger(path).snapshot()["calls"] == {"groq": 2, "cloudflare": 0}


@pytest.mark.parametrize(
    "limits",
    [
        {"groq": 0, "cloudflare": 1},
        {"groq": 41, "cloudflare": 1},
        {"groq": True, "cloudflare": 1},
        {"groq": 1},
    ],
)
def test_invalid_verification_limits_are_rejected_before_creating_ledger(tmp_path, limits):
    path = tmp_path / "invalid.sqlite"
    with pytest.raises(ValueError, match="INVALID_DEMO_LIMITS"):
        Ledger(path, limits=limits)
    assert not path.exists()


def test_context_evidence_client_shares_the_same_verification_ceiling(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from pydantic import SecretStr

    from contextbridge.runtime import IntegrationBackends
    from scripts.v1 import factory

    path = tmp_path / "context.sqlite"
    Ledger(path, limits={"groq": 1, "cloudflare": 1})
    clients = [SimpleNamespace() for _ in range(3)]
    backends = IntegrationBackends(
        extraction_provider=SimpleNamespace(client=clients[0]),
        evidence_judge=SimpleNamespace(client=clients[1]),
        context_evidence_judge=SimpleNamespace(client=clients[2]),
    )
    monkeypatch.setenv("CONTEXTBRIDGE_V1_DEMO_LEDGER", str(path))
    monkeypatch.setattr(factory, "hosted_backends", lambda *a: backends)
    monkeypatch.setattr(factory, "CloudflareEmbeddingBackend", lambda **kw: SimpleNamespace(**kw))
    factory.make(
        SimpleNamespace(
            database_url=SecretStr("postgresql://127.0.0.1/contextbridge_v1_live_test"),
            developer_id="v1-demo-fixture",
            capture_project_id="v1-synthetic-demo",
            embedding_api_key=SecretStr("synthetic-only"),
            embedding_base_url=SecretStr("https://synthetic.invalid"),
            embedding_model_id="synthetic-model",
            embedding_dimensions=2,
            provider_timeout_seconds=5,
        ),
        None,
    )
    requests = []
    for client in clients:
        assert isinstance(client.transport, BudgetTransport)
        client.transport.transport = httpx.MockTransport(
            lambda r: (requests.append(r), httpx.Response(200, content=b"synthetic"))[1]
        )
    request = httpx.Request("POST", "https://synthetic.invalid")
    clients[2].transport.handle_request(request)
    with pytest.raises(ModuleError, match="CANCELLED"):
        clients[0].transport.handle_request(request)
    assert len(requests) == 1
