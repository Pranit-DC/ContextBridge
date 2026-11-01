import json
import traceback

import httpx
import pytest
from pydantic import ValidationError

from contextbridge.config import Settings
from contextbridge.engine.errors import ModuleError
from contextbridge.retrieval.cloudflare import (
    DIMENSIONS,
    MAX_RESPONSE_BYTES,
    MODEL_ID,
    QUERY_INSTRUCTION,
    CloudflareEmbeddingBackend,
)
from contextbridge.retrieval.embedding import GuardedEmbeddingProvider
from contextbridge.retrieval.retriever import Retriever
from tests.conftest import TEST_TOKEN

BASE_URL = "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/v1"
SYNTHETIC_KEY = "synthetic-cloudflare-test-key"


def configuration(**changes):
    return Settings(
        _env_file=None,
        **{
            "database_url": "postgresql+psycopg://unused/unused_test",
            "api_token": TEST_TOKEN,
            "embedding_provider": "cloudflare",
            "embedding_api_key": SYNTHETIC_KEY,
            "embedding_base_url": BASE_URL,
            "embedding_model_id": MODEL_ID,
            **changes,
        },
    )


def response(vectors=None, **changes):
    vectors = vectors if vectors is not None else [[1.0] + [0.0] * (DIMENSIONS - 1)]
    return {
        "model": MODEL_ID,
        "data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)],
        **changes,
    }


def backend(handler, **changes):
    return CloudflareEmbeddingBackend(
        **{
            "api_key": SYNTHETIC_KEY,
            "base_url": BASE_URL,
            "transport": httpx.MockTransport(handler),
            **changes,
        }
    )


def test_known_model_defaults_dimensions_and_hides_credentials():
    settings = configuration()
    assert settings.embedding_dimensions == DIMENSIONS and settings.embedding_only
    assert SYNTHETIC_KEY not in repr(settings) and BASE_URL not in repr(settings)
    assert "embedding_api_key" not in settings.model_dump()
    assert "embedding_base_url" not in settings.model_dump()
    assert not configuration(
        integration_factory="tests.integration.provider_factory:make"
    ).embedding_only


@pytest.mark.parametrize(
    "changes",
    [
        {"embedding_dimensions": 384},
        {"embedding_model_id": "different-model"},
        {"embedding_api_key": None},
        {"embedding_api_key": " "},
        {"embedding_base_url": None},
        {"embedding_base_url": "http://localhost/ai/v1"},
        {"embedding_base_url": BASE_URL + "?key=secret"},
        {"embedding_base_url": BASE_URL + "/embeddings"},
        {"embedding_base_url": BASE_URL.replace("api.cloudflare.com", "api.cloudflare.com.evil")},
        {"embedding_base_url": BASE_URL.replace("https://", "https://user:secret@")},
        {"embedding_provider": "unknown-provider"},
        {"worker_factory": "tests.background.worker_factory:make"},
    ],
)
def test_bad_configuration_fails_without_echoing_settings(changes):
    with pytest.raises(ValidationError) as error:
        configuration(**changes)
    assert SYNTHETIC_KEY not in str(error.value) and BASE_URL not in str(error.value)


def test_documents_are_unchanged_queries_are_instructed_and_indices_restore_order():
    requests = []

    def handler(request):
        assert request.url.path.endswith("/ai/v1/embeddings")
        assert request.headers["Authorization"] == f"Bearer {SYNTHETIC_KEY}"
        body = json.loads(request.content)
        requests.append(body)
        vectors = [[float(i + 1)] + [0.0] * (DIMENSIONS - 1) for i in range(len(body["input"]))]
        return httpx.Response(200, json=response(vectors, data=response(vectors)["data"][::-1]))

    provider = GuardedEmbeddingProvider(backend(handler), model_id=MODEL_ID, dimensions=DIMENSIONS)
    assert [v[0] for v in provider.embed(["first document", "second document"])["vectors"]] == [
        1,
        2,
    ]
    assert provider.embed_query("durable datastore")["dimensions"] == DIMENSIONS
    assert requests[0]["input"] == ["first document", "second document"]
    assert requests[1]["input"] == [f"Instruct: {QUERY_INSTRUCTION}\nQuery: durable datastore"]
    assert all(r["model"] == MODEL_ID and r["encoding_format"] == "float" for r in requests)
    assert Retriever()._embed(provider, "durable datastore").dimensions == DIMENSIONS


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        response(data=[]),
        response(data="wrong"),
        response(data=[None]),
        response(model="wrong-model"),
        response(data=[{"index": True, "embedding": [1.0] * DIMENSIONS}]),
        response(data=[{"index": -1, "embedding": [1.0] * DIMENSIONS}]),
        response(data=[{"index": 1, "embedding": [1.0] * DIMENSIONS}]),
        response(data=[{"embedding": [1.0] * DIMENSIONS}]),
        response([[1.0]]),
        response([["1.0"] * DIMENSIONS]),
        response([[True] * DIMENSIONS]),
        response([[float("nan")] * DIMENSIONS]),
        response([[float("inf")] * DIMENSIONS]),
        response([[1e40] * DIMENSIONS]),
    ],
)
def test_malformed_output_is_rejected(payload):
    # json.dumps permits NaN/Infinity here, deliberately exercising the strict boundary.
    client = backend(lambda request: httpx.Response(200, content=json.dumps(payload)))
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        client.embed_batch(["document"])


def test_duplicate_indices_are_rejected():
    rows = response([[1.0] * DIMENSIONS, [2.0] * DIMENSIONS])["data"]
    rows[1]["index"] = 0
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        backend(lambda request: httpx.Response(200, json=response(data=rows))).embed_batch(
            ["a", "b"]
        )


@pytest.mark.parametrize(
    "status,retryable",
    [(401, False), (403, False), (429, True), (503, True), (408, True), (400, False), (302, False)],
)
def test_http_errors_are_sanitized_and_do_not_retry_or_follow_redirects(status, retryable):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, content=SYNTHETIC_KEY, headers={"Location": "https://evil.example"}
        )

    with pytest.raises(ModuleError) as error:
        backend(handler).embed_batch(["document"])
    assert error.value.code == "EMBEDDING_UNAVAILABLE" and error.value.retryable is retryable
    assert len(calls) == 1
    assert SYNTHETIC_KEY not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError, RuntimeError])
def test_transport_failure_has_no_exception_chain(exception):
    def handler(request):
        raise exception(SYNTHETIC_KEY)

    with pytest.raises(ModuleError) as error:
        backend(handler).embed_batch(["document"])
    assert error.value.retryable and error.value.code == "EMBEDDING_UNAVAILABLE"
    assert SYNTHETIC_KEY not in "".join(traceback.format_exception(error.value))


@pytest.mark.parametrize(
    "texts",
    [["x" * 8193], ["🙂" * 2049], ["\ud800"], ["password=secret"], [" "], ["a"] * 33, "document"],
)
def test_oversize_invalid_and_secret_input_never_reaches_transport(texts):
    def never(request):
        pytest.fail("Invalid text reached the provider")

    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        backend(never).embed_batch(texts)


def test_query_instruction_counts_towards_input_bound():
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        backend(lambda request: pytest.fail("Oversize query was sent")).embed_query_batch(
            ["x" * 8192]
        )


@pytest.mark.parametrize(
    "content,headers",
    [(b"x" * (MAX_RESPONSE_BYTES + 1), {}), (b"not json", {}), (b"", {"Content-Encoding": "gzip"})],
    ids=["oversize-response", "invalid-json", "compressed-response"],
)
def test_response_body_is_bounded_and_invalid_json_is_safe(content, headers):
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        backend(lambda request: httpx.Response(200, content=content, headers=headers)).embed_batch(
            ["a"]
        )


def test_no_network_for_empty_batch():
    assert backend(lambda request: pytest.fail("Empty batch was sent")).embed_batch([]) == []


def test_escaped_json_request_is_bounded_before_transport():
    client = backend(lambda request: pytest.fail("Oversize JSON was sent"))
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        client.embed_batch(["x" + "\x00" * 8191] * 32)


def test_client_disables_redirects_and_ambient_proxies(monkeypatch):
    original = httpx.Client
    options = []

    def client(**kwargs):
        options.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    backend(lambda request: httpx.Response(200, json=response())).embed_batch(["a"])
    assert options[0]["trust_env"] is False and options[0]["follow_redirects"] is False
