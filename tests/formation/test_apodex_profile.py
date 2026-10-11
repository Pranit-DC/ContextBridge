"""Synthetic transport fixtures for the selected Apodex profile, never model scores."""

import json
from types import SimpleNamespace

import httpx
import pytest

from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.config import FormationSettings
from scripts.formation import verify_free as runner
from scripts.formation.evaluate import fixture_candidate, load_dataset

MODEL = "apodex/apodex-1.1-mini:free"
KEY = "synthetic-apodex-test-key-123456"


def configured():
    return FormationSettings(
        _env_file=None,
        provider="openrouter",
        model=MODEL,
        verifier_model=MODEL,
        api_key=KEY,
        response_format="json_object",
        allow_hosted=True,
        allow_paid=False,
        openrouter_free_only=True,
        openrouter_data_collection="deny",
    )


def envelope(value):
    return {
        "model": "apodex/apodex-1.1-mini",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(value)},
            }
        ],
        "usage": {"prompt_tokens": 123, "completion_tokens": 45, "cost": 0},
    }


def inject_transport(monkeypatch, handler):
    original = ChatClient.__init__

    def initialize(self, settings):
        original(self, settings, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(ChatClient, "__init__", initialize)


CASES = [
    (split, case.case_id)
    for split in ("tuning", "holdout")
    for case in load_dataset(split)[0].cases
]


@pytest.mark.parametrize("split,case_id", CASES)
def test_fixed_case_with_apodex_protocol_fixture(monkeypatch, split, case_id):
    dataset, _ = load_dataset(split)
    case = next(case for case in dataset.cases if case.case_id == case_id)
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == MODEL
        assert body["response_format"] == {"type": "json_object"}
        assert "The required output JSON Schema is:" in body["messages"][0]["content"]
        assert body["provider"] == {
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
            "max_price": {"prompt": 0, "completion": 0, "request": 0},
        }
        assert KEY not in request.content.decode()
        assert request.headers["Authorization"] == "Bearer " + KEY
        payload = json.loads(body["messages"][1]["content"])
        if "candidate" in payload:
            value = {"support": "supported"}
        else:
            assert payload == case.event.model_dump(mode="json")
            candidates = []
            for claim in case.expected_claims:
                candidate = fixture_candidate(case, claim).model_dump(mode="json")
                candidate["conditions"] = [
                    {"key": key, "value": value} for key, value in candidate["conditions"].items()
                ]
                candidates.append(candidate)
            value = {"candidates": candidates}
        return httpx.Response(200, json=envelope(value))

    inject_transport(monkeypatch, handler)
    telemetry = []
    predictions, calls = runner.measure(
        SimpleNamespace(cases=[case]),
        configured(),
        8,
        telemetry=telemetry,
        gate=runner.RequestGate(0),
    )
    prediction = predictions[0]
    assert prediction.error_code is None
    assert [candidate.content for candidate in prediction.proposals] == [
        claim.content for claim in case.expected_claims
    ]
    assert [decision.outcome for decision in prediction.decisions] == [
        claim.expected_admission for claim in case.expected_claims
    ]
    assert calls == len(requests)
    assert calls <= 1 + len(case.expected_claims)
    assert all(call["observed_model"] == "apodex/apodex-1.1-mini" for call in telemetry)
    if not requests:
        assert prediction.latency_ms is None
        assert prediction.cost is None


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 429, 500, 503])
def test_apodex_http_failure_stops_after_one_attempt(monkeypatch, status, capsys):
    dataset, _ = load_dataset("tuning")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, text="private provider payload " + KEY)

    inject_transport(monkeypatch, handler)
    telemetry, cases = [], []
    predictions, calls = runner.measure(
        SimpleNamespace(cases=dataset.cases[:2]),
        configured(),
        8,
        telemetry=telemetry,
        case_telemetry=cases,
        gate=runner.RequestGate(0),
    )
    assert calls == len(requests) == 1
    assert telemetry[0]["http_status"] == status
    assert telemetry[0]["retryable"] is (status == 429 or status >= 500)
    assert all(case.error_code == "PROVIDER_UNAVAILABLE" for case in predictions)
    assert cases[1]["execution"] == "provider_stop"
    assert telemetry[0]["observed_model"] is None
    assert all(case.cost is None for case in predictions)
    assert KEY not in capsys.readouterr().out
    assert "private provider payload" not in json.dumps(telemetry)


@pytest.mark.parametrize(
    "finish_reason,content", [("length", {}), ("stop", {}), ("stop", {"candidates": "guess"})]
)
def test_apodex_incomplete_or_invalid_contract_retains_usage_without_admission(
    monkeypatch, finish_reason, content
):
    dataset, _ = load_dataset("tuning")

    def handler(request):
        response = envelope(content)
        response["choices"][0]["finish_reason"] = finish_reason
        return httpx.Response(200, json=response)

    inject_transport(monkeypatch, handler)
    telemetry = []
    predictions, calls = runner.measure(
        SimpleNamespace(cases=dataset.cases[:1]),
        configured(),
        8,
        telemetry=telemetry,
        gate=runner.RequestGate(0),
    )
    assert calls == 1
    assert predictions[0].error_code == "INVALID_PROVIDER_OUTPUT"
    assert predictions[0].decisions == []
    assert predictions[0].input_tokens == 123
    assert predictions[0].cost == 0
    assert telemetry[0]["http_status"] == 200


@pytest.mark.parametrize("verdict", ["unsupported", "uncertain"])
def test_apodex_verifier_disagreement_never_admits_fixture_claim(monkeypatch, verdict):
    dataset, _ = load_dataset("tuning")
    case = dataset.cases[0]
    candidate = fixture_candidate(case, case.expected_claims[0]).model_dump(mode="json")
    candidate["conditions"] = []

    def handler(request):
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        return httpx.Response(
            200,
            json=envelope(
                {"support": verdict} if "candidate" in payload else {"candidates": [candidate]}
            ),
        )

    inject_transport(monkeypatch, handler)
    predictions, calls = runner.measure(
        SimpleNamespace(cases=[case]), configured(), 8, gate=runner.RequestGate(0)
    )
    assert calls == 2
    assert predictions[0].error_code == "INVALID_PROVIDER_OUTPUT"
    assert predictions[0].decisions == []
    assert len(predictions[0].proposals) == 1  # Untrusted review artifact, never stored memory.


@pytest.mark.parametrize("received_headers", [False, True])
def test_apodex_timeout_stops_calls_even_after_http_200_headers(monkeypatch, received_headers):
    dataset, _ = load_dataset("tuning")
    requests = []

    class FailingStream(httpx.SyncByteStream):
        def __iter__(self):
            raise httpx.ReadTimeout("private provider payload " + KEY)
            yield b""  # A streaming generator that fails before a complete response.

    def handler(request):
        requests.append(request)
        if received_headers:
            return httpx.Response(200, stream=FailingStream())
        raise httpx.ReadTimeout("private provider payload " + KEY, request=request)

    inject_transport(monkeypatch, handler)
    telemetry, cases = [], []
    predictions, calls = runner.measure(
        SimpleNamespace(cases=dataset.cases[:2]),
        configured(),
        8,
        telemetry=telemetry,
        case_telemetry=cases,
        gate=runner.RequestGate(0),
    )
    assert calls == len(requests) == 1
    assert telemetry[0]["http_status"] == (200 if received_headers else None)
    assert telemetry[0]["retryable"] is True
    assert telemetry[0]["input_tokens"] is None
    assert telemetry[0]["cost_usd"] is None
    assert predictions[0].proposals == predictions[0].decisions == []
    assert predictions[1].latency_ms is None
    assert cases[1]["execution"] == "provider_stop"
    assert KEY not in json.dumps(telemetry)
