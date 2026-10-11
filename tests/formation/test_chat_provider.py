import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.chat import (
    MAX_RESPONSE_BYTES,
    ChatClient,
    ChatEvidenceVerifier,
    ChatModelProvider,
    ExtractionResponse,
    VerificationResponse,
    strict_schema,
)
from contextbridge.formation.providers.config import FormationSettings

KEY = "synthetic-test-key-123456"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    import os

    for key in list(os.environ):
        if key.upper().startswith("CONTEXTBRIDGE_FORMATION_"):
            monkeypatch.delenv(key)


def configuration(**changes):
    return FormationSettings(
        _env_file=None,
        **(
            {
                "provider": "openrouter",
                "model": "example/model:free",
                "api_key": KEY,
                "allow_hosted": True,
            }
            | changes
        ),
    )


def envelope(content, **changes):
    return {
        "model": "example/model:free",
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ],
        **changes,
    }


def wire_candidate(candidate):
    result = copy.deepcopy(candidate)
    result["conditions"] = [
        {"key": key, "value": value} for key, value in candidate["conditions"].items()
    ]
    return result


def injected(response, **changes):
    def handler(request):
        return httpx.Response(200, json=response)

    return ChatClient(configuration(**changes), transport=httpx.MockTransport(handler))


def fail_safely(operation, code="INVALID_PROVIDER_OUTPUT", retryable=False):
    with pytest.raises(ModuleError) as caught:
        operation()
    assert caught.value.code == code
    assert caught.value.retryable is retryable
    assert KEY not in str(caught.value)


def test_transport_options_and_contract_conversion(event, candidate):
    observed = []

    def handler(request):
        observed.append(request)
        return httpx.Response(
            200, json=envelope(json.dumps({"candidates": [wire_candidate(candidate)]}))
        )

    client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
    assert json.loads(ChatModelProvider(client).generate(event)) == [candidate]
    request = observed[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer " + KEY
    body = json.loads(request.content)
    assert body["model"] == "example/model:free"
    assert body["stream"] is False
    assert body["max_tokens"] == 8192
    assert body["provider"] == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "max_price": {"prompt": 0, "completion": 0, "request": 0},
    }
    assert KEY not in request.content.decode()
    assert not {"tools", "plugins", "models", "route", "debug"} & body.keys()
    assert body["response_format"]["json_schema"]["strict"] is True
    assert json.loads(body["messages"][1]["content"]) == event
    assert client.last_observation.input_tokens is None
    assert client.last_observation.cost_usd is None


def test_strict_schema_closes_objects_and_requires_nullable_fields():
    def inspect(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            assert "default" not in value
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(strict_schema(ExtractionResponse))


def test_json_object_mode_still_validates_contract(event, candidate):
    client = injected(
        envelope(json.dumps({"candidates": [wire_candidate(candidate)]})),
        response_format="json_object",
    )
    assert json.loads(ChatModelProvider(client).generate(event)) == [candidate]
    candidate["confidence"] = "0.9"
    client = injected(
        envelope(json.dumps({"candidates": [wire_candidate(candidate)]})),
        response_format="json_object",
    )
    fail_safely(lambda: ChatModelProvider(client).generate(event))


@pytest.mark.parametrize("schema", [ExtractionResponse, VerificationResponse])
def test_json_object_provider_receives_trusted_contract_schema(event, schema):
    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        supplied = body["messages"][0]["content"].split("The required output JSON Schema is:\n", 1)[
            1
        ]
        assert json.loads(supplied) == strict_schema(schema)
        assert json.loads(body["messages"][1]["content"]) == event
        return httpx.Response(200, json=envelope("{}"))

    client = ChatClient(
        configuration(response_format="json_object"), transport=httpx.MockTransport(handler)
    )
    client.complete(client.settings.model, "Return JSON only.", event, schema)


def test_separate_verifier_and_admission_with_comparison_context(event, candidate, context):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["response_format"]["json_schema"]["name"] == "ExtractionResponse":
            content = {"candidates": [wire_candidate(candidate)]}
        else:
            content = {"support": "supported"}
            assert body["model"] == "example/verifier:free"
        return httpx.Response(200, json=envelope(json.dumps(content)))

    client = ChatClient(
        configuration(verifier_model="example/verifier:free"),
        transport=httpx.MockTransport(handler),
    )
    verifier = ChatEvidenceVerifier(client)
    proposals = Extractor(ChatModelProvider(client), verifier).extract(event)
    policy = AdmissionPolicy(verifier, lambda event_id: event)
    assert policy.assess(proposals[0], context)["outcome"] == "ADMIT"
    assert len(calls) == 3
    assert calls[1]["messages"][0]["content"] != calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("verdict", ["unsupported", "uncertain"])
def test_verifier_disagreement_blocks_guessed_memory(event, candidate, verdict):
    provider = ChatModelProvider(
        injected(envelope(json.dumps({"candidates": [wire_candidate(candidate)]})))
    )
    verifier = ChatEvidenceVerifier(injected(envelope(json.dumps({"support": verdict}))))
    fail_safely(lambda: Extractor(provider, verifier).extract(event))


@pytest.mark.parametrize(
    "mutation", ["scope", "assistant", "quote", "event", "conditions", "duplicate-id"]
)
def test_invalid_provenance_and_duplicate_conditions_fail(event, candidate, mutation):
    proposed = wire_candidate(candidate)
    if mutation == "scope":
        proposed["project_id"] = "another-project"
    elif mutation == "assistant":
        event["messages"][0]["role"] = "assistant"
        event["messages"].append({"message_id": "filler", "role": "user", "content": "Thanks"})
    elif mutation == "quote":
        proposed["source"]["evidence"] = "An invented excerpt"
    elif mutation == "event":
        proposed["evidence_refs"][0]["message_id"] = "unknown"
    elif mutation == "conditions":
        proposed["conditions"] = [
            {"key": "environment", "value": "prod"},
            {"key": "environment", "value": "dev"},
        ]
    candidates = [proposed, proposed] if mutation == "duplicate-id" else [proposed]
    fail_safely(
        lambda: ChatModelProvider(
            injected(envelope(json.dumps({"candidates": candidates})))
        ).generate(event)
    )


@pytest.mark.parametrize(
    "response",
    [
        {"error": {"message": "private upstream error"}},
        {"choices": []},
        envelope("not JSON"),
        envelope('{"candidates":[],"candidates":[]}'),
        envelope('{"candidates":[],"score":NaN}'),
        envelope(json.dumps({"candidates": [], "api_key": "private-secret"})),
        envelope(json.dumps({"candidates": [], "note": KEY})),
        {
            "choices": [
                {"finish_reason": "length", "message": {"role": "assistant", "content": "{}"}}
            ]
        },
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "{}", "refusal": "private"},
                }
            ]
        },
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "{}",
                        "tool_calls": [{"name": "write_db"}],
                    },
                }
            ]
        },
        {"choices": [{"finish_reason": "stop", "message": {"role": "user", "content": "{}"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": []}}]},
    ],
)
def test_refusals_malformed_output_and_secrets_fail_safely(event, response, caplog):
    fail_safely(lambda: ChatModelProvider(injected(response)).generate(event))
    assert "private" not in caplog.text
    assert KEY not in caplog.text


@pytest.mark.parametrize(
    "status,retryable", [(401, False), (403, False), (400, False), (429, True), (503, True)]
)
def test_http_status_is_sanitized_without_reading_error_body(event, status, retryable, caplog):
    def handler(request):
        return httpx.Response(status, text="private transcript " + KEY)

    client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
    fail_safely(
        lambda: ChatModelProvider(client).generate(event), "PROVIDER_UNAVAILABLE", retryable
    )
    assert client.last_observation is None
    assert KEY not in caplog.text


def test_timeout_is_retryable_and_does_not_echo_provider_exception(event):
    def handler(request):
        raise httpx.ReadTimeout("private input " + KEY, request=request)

    client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
    fail_safely(lambda: ChatModelProvider(client).generate(event), "PROVIDER_UNAVAILABLE", True)


def test_redirect_never_forwards_key_to_another_endpoint(event):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(307, headers={"Location": "https://another.example/v1"})

    client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
    fail_safely(lambda: ChatModelProvider(client).generate(event), "PROVIDER_UNAVAILABLE")
    assert len(requests) == 1


def test_oversized_and_non_utf8_responses_fail(event):
    for content in (b" " * (MAX_RESPONSE_BYTES + 1), b"\xff"):

        def handler(request, content=content):
            return httpx.Response(200, content=content)

        client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
        fail_safely(lambda client=client: ChatModelProvider(client).generate(event))


def test_telemetry_preserves_observed_zero_and_unknowns(event):
    usage = {"prompt_tokens": 120, "completion_tokens": 0, "cost": 0}
    client = injected(envelope('{"candidates":[]}', usage=usage))
    assert ChatModelProvider(client).generate(event) == "[]"
    assert client.last_observation.model == "example/model:free"
    assert client.last_observation.input_tokens == 120
    assert client.last_observation.output_tokens == 0
    assert client.last_observation.cost_usd == 0
    assert client.last_observation.latency_seconds >= 0
    client = injected(
        envelope(
            '{"candidates":[]}', usage={"prompt_tokens": True, "completion_tokens": -1, "cost": "0"}
        )
    )
    ChatModelProvider(client).generate(event)
    assert client.last_observation.input_tokens is None
    assert client.last_observation.output_tokens is None
    assert client.last_observation.cost_usd is None


def test_invalid_model_output_retains_only_safe_transport_usage(event):
    client = injected(
        envelope("not JSON", usage={"prompt_tokens": 17, "completion_tokens": 9, "cost": 0})
    )
    fail_safely(lambda: ChatModelProvider(client).generate(event))
    assert client.last_observation.model == "example/model:free"
    assert client.last_observation.input_tokens == 17
    assert client.last_observation.output_tokens == 9
    assert client.last_observation.cost_usd == 0


def test_escaped_configured_key_cannot_be_returned_as_content(event):
    escaped_key = KEY.replace("-", r"\u002d")
    response = envelope('{"candidates":[],"note":"' + escaped_key + '"}')
    fail_safely(lambda: ChatModelProvider(injected(response)).generate(event))


def test_malformed_semantic_verifier_output_is_not_support(event, candidate):
    for result in ({"support": "maybe"}, {"support": "supported", "reason": "trust me"}):
        verifier = ChatEvidenceVerifier(injected(envelope(json.dumps(result))))
        fail_safely(lambda verifier=verifier: verifier.verify(candidate, event))


def test_missing_hosted_consent_blocks_transport(event):
    def handler(request):
        pytest.fail("Hosted consent is required")

    client = ChatClient(configuration(allow_hosted=False), transport=httpx.MockTransport(handler))
    fail_safely(lambda: ChatModelProvider(client).generate(event), "INVALID_INPUT")


def test_input_secrets_and_unselected_models_never_call_http(event):
    def handler(request):
        pytest.fail("Invalid input must never reach transport")

    client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
    fail_safely(
        lambda: client.complete("example/paid", "prompt", event, VerificationResponse),
        "INVALID_INPUT",
    )
    event["messages"][0]["content"] = KEY
    fail_safely(lambda: ChatModelProvider(client).generate(event), "INVALID_INPUT")
    event["messages"][0]["content"] = "api_key=private"
    fail_safely(lambda: ChatModelProvider(client).generate(event), "INVALID_INPUT")


def test_assistant_only_and_invalid_verifier_provenance_never_call_http(event, candidate):
    def handler(request):
        pytest.fail("No model call is warranted")

    client = ChatClient(configuration(), transport=httpx.MockTransport(handler))
    candidate["project_id"] = "other-project"
    assert ChatEvidenceVerifier(client).verify(candidate, event) == "unsupported"
    event["messages"][0]["role"] = "assistant"
    assert ChatModelProvider(client).generate(event) == "[]"


def test_real_loopback_http_transport_without_model_or_database(event, candidate):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(
                (self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            )
            body = json.dumps(
                envelope(json.dumps({"candidates": [wire_candidate(candidate)]}))
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        configured = configuration(
            provider="ollama",
            model="local-model",
            api_key=None,
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
        )
        assert json.loads(ChatModelProvider(ChatClient(configured)).generate(event)) == [candidate]
        assert requests[0][0] == "/v1/chat/completions"
        assert requests[0][1]["model"] == "local-model"
        assert "provider" not in requests[0][1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
