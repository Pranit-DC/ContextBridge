import math
import time

import pytest

from contextbridge.contracts import EmbeddingBatch
from contextbridge.engine.errors import ModuleError
from contextbridge.retrieval.embedding import FakeEmbeddingProvider, GuardedEmbeddingProvider


class Backend:
    def __init__(self, dimensions=2, result=None, error=None, delay=0.0):
        self.dimensions = dimensions
        self.result = result
        self.error = error
        self.delay = delay
        self.batches: list[list[str]] = []

    def embed_batch(self, texts):
        self.batches.append(texts)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        if self.result is not None:
            return self.result
        return [[float(len(t)), 1.0][: self.dimensions] for t in texts]


def guarded(backend, **overrides):
    options = {"model_id": "m1", "dimensions": 2, **overrides}
    return GuardedEmbeddingProvider(backend, **options)


def test_output_is_labelled_validated_and_in_input_order():
    batch = guarded(Backend()).embed(["a", "bb", "ccc"])
    EmbeddingBatch.model_validate(batch)
    assert (batch["model_id"], batch["dimensions"]) == ("m1", 2)
    assert [v[0] for v in batch["vectors"]] == [1.0, 2.0, 3.0]


def test_texts_are_sent_in_bounded_batches():
    backend = Backend()
    batch = guarded(backend, batch_size=2).embed(["a", "b", "c", "d", "e"])
    assert [len(b) for b in backend.batches] == [2, 2, 1]
    assert len(batch["vectors"]) == 5


def test_empty_input_makes_no_backend_call():
    backend = Backend()
    assert guarded(backend).embed([])["vectors"] == []
    assert backend.batches == []


def test_optional_query_method_falls_back_for_existing_backends():
    backend = Backend()
    provider = guarded(backend)
    assert provider.embed_query("a") == provider.embed(["a"])
    assert backend.batches == [["a"], ["a"]]


@pytest.mark.parametrize(
    "result",
    [
        [[1.0, 2.0]],  # one vector too few for two texts
        [[1.0, 2.0], [1.0]],  # wrong dimensions
        [[1.0, 2.0], [float("nan"), 1.0]],
        [[1.0, 2.0], [float("inf"), 1.0]],
        "not vectors",
        {"vectors": 1},
        [[1.0, 2.0], ["x", "y"]],
    ],
)
def test_malformed_backend_output_is_rejected_safely(result):
    with pytest.raises(ModuleError) as raised:
        guarded(Backend(result=result)).embed(["a", "b"])
    assert raised.value.code == "INVALID_PROVIDER_OUTPUT"


def test_backend_failure_is_retryable_and_leaks_no_provider_text():
    provider = guarded(Backend(error=RuntimeError("token=hunter2 at http://internal")))
    with pytest.raises(ModuleError) as raised:
        provider.embed(["a"])
    assert (raised.value.code, raised.value.retryable) == ("EMBEDDING_UNAVAILABLE", True)
    assert "hunter2" not in str(raised.value) and raised.value.__cause__ is None


def test_backend_module_errors_pass_through():
    provider = guarded(Backend(error=ModuleError("PROVIDER_UNAVAILABLE", retryable=True)))
    with pytest.raises(ModuleError) as raised:
        provider.embed(["a"])
    assert raised.value.code == "PROVIDER_UNAVAILABLE"


def test_a_slow_backend_times_out_promptly():
    provider = guarded(Backend(delay=1.0), timeout_seconds=0.05)
    started = time.monotonic()
    with pytest.raises(ModuleError) as raised:
        provider.embed(["a"])
    assert (raised.value.code, raised.value.retryable) == ("EMBEDDING_UNAVAILABLE", True)
    assert time.monotonic() - started < 0.5


def test_the_deadline_covers_all_batches_together():
    provider = guarded(Backend(delay=0.08), batch_size=1, timeout_seconds=0.12)
    with pytest.raises(ModuleError) as raised:
        provider.embed(["a", "b", "c", "d"])
    assert raised.value.code == "EMBEDDING_UNAVAILABLE"


@pytest.mark.parametrize(
    "texts",
    [
        ["token: sk-abcdefghijklmnopqrstuvwxyz"],
        ["password=hunter2"],
        ["ok", "   "],
        ["x" * 8001],
        [123],
        "a string, not a list",
        ["a"] * 101,
    ],
)
def test_bad_input_is_rejected_before_any_backend_call(texts):
    backend = Backend()
    with pytest.raises(ModuleError) as raised:
        guarded(backend).embed(texts)
    assert raised.value.code == "INVALID_INPUT"
    assert backend.batches == []


def test_the_secret_is_not_echoed_in_the_error():
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    with pytest.raises(ModuleError) as raised:
        guarded(Backend()).embed([secret])
    assert secret not in str(raised.value) and secret not in repr(raised.value.args)


@pytest.mark.parametrize(
    "bad",
    [
        {"model_id": ""},
        {"dimensions": 0},
        {"dimensions": 5000},
        {"batch_size": 0},
        {"max_texts": 0},
        {"timeout_seconds": 0},
    ],
)
def test_invalid_configuration_is_rejected(bad):
    with pytest.raises(ValueError):
        guarded(Backend(), **bad)


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_provider_is_deterministic_and_normalized():
    fake = FakeEmbeddingProvider(dimensions=32)
    first, second = fake.embed(["use postgres"]), fake.embed(["use postgres"])
    assert first == second
    EmbeddingBatch.model_validate(first)
    assert math.isclose(sum(v * v for v in first["vectors"][0]), 1.0)


def test_fake_provider_rewards_shared_words_only():
    fake = FakeEmbeddingProvider(dimensions=256)
    base, near, far = fake.embed(
        ["database postgres primary", "primary postgres database choice", "logging format json"]
    )["vectors"]
    assert cosine(base, near) > cosine(base, far)


def test_fake_provider_handles_empty_text():
    vector = FakeEmbeddingProvider(dimensions=8).embed([""])["vectors"][0]
    assert len(vector) == 8 and all(math.isfinite(v) for v in vector)


def test_fake_provider_rejects_invalid_dimensions():
    with pytest.raises(ValueError):
        FakeEmbeddingProvider(dimensions=0)
