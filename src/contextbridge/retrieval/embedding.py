"""Guarded injected embedding backends and an explicitly synthetic test provider."""

import hashlib
import math
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from time import monotonic
from typing import Protocol

from pydantic import ValidationError

from contextbridge.contracts import EmbeddingBatch
from contextbridge.contracts.messages import MAX_EMBEDDING_DIMENSIONS
from contextbridge.engine.errors import ModuleError
from contextbridge.security import contains_secret

MAX_TEXT_CHARS = 8000


class EmbeddingBackend(Protocol):
    """The model call. Must return one vector of the declared size per input text."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class GuardedEmbeddingProvider:
    """Validates input and output around a backend; failures surface as safe ModuleErrors.

    - Input: bounded count and length; credentials are rejected before any backend call.
    - Calls: fixed batch size and one overall deadline. A timed-out call cannot be killed, only
      abandoned; its worker thread may keep running until the backend returns.
    - Output: exactly one finite vector of the declared dimensions per text, labelled with the
      declared model so incompatible vectors are never compared.
    - Errors carry only a code, never provider text.
    """

    def __init__(
        self,
        backend: EmbeddingBackend,
        *,
        model_id: str,
        dimensions: int,
        batch_size: int = 32,
        max_texts: int = 100,
        timeout_seconds: float = 10.0,
    ):
        if (
            not model_id
            or not 1 <= dimensions <= MAX_EMBEDDING_DIMENSIONS
            or batch_size < 1
            or max_texts < 1
            or not timeout_seconds > 0
        ):
            raise ValueError("Invalid embedding provider configuration")
        self.backend = backend
        self.model_id = model_id
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.max_texts = max_texts
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> dict:
        return self._embed(texts, self.backend.embed_batch)

    def embed_query(self, text: str) -> dict:
        method = getattr(self.backend, "embed_query_batch", None)
        return self._embed([text], method if callable(method) else self.backend.embed_batch)

    def _embed(self, texts, method) -> dict:
        self._check_input(texts)
        deadline = monotonic() + self.timeout_seconds
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._call(batch, deadline, method))
        return {"model_id": self.model_id, "dimensions": self.dimensions, "vectors": vectors}

    def _check_input(self, texts: list[str]) -> None:
        if not isinstance(texts, list) or len(texts) > self.max_texts:
            raise ModuleError("INVALID_INPUT")
        for text in texts:
            if (
                not isinstance(text, str)
                or not text.strip()
                or len(text) > MAX_TEXT_CHARS
                or contains_secret(text)
            ):
                raise ModuleError("INVALID_INPUT")

    def _call(self, batch: list[str], deadline: float, method) -> list[list[float]]:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ModuleError("EMBEDDING_UNAVAILABLE", retryable=True)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            raw = executor.submit(method, list(batch)).result(timeout=remaining)
        except FutureTimeout:
            raise ModuleError("EMBEDDING_UNAVAILABLE", retryable=True) from None
        except ModuleError as error:
            raise ModuleError(error.code, retryable=error.retryable) from None
        except Exception:
            raise ModuleError("EMBEDDING_UNAVAILABLE", retryable=True) from None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return self._validated(raw, len(batch))

    def _validated(self, raw: object, expected: int) -> list[list[float]]:
        try:
            checked = EmbeddingBatch.model_validate(
                {"model_id": self.model_id, "dimensions": self.dimensions, "vectors": raw}
            )
        except (ValidationError, TypeError, ValueError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
        if len(checked.vectors) != expected:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return checked.vectors


class FakeEmbeddingProvider:
    """Deterministic word-hashing vectors for tests and demos.

    Texts sharing words get similar vectors. It captures no meaning, so it must never be
    presented as semantic retrieval or used to report retrieval quality.
    """

    def __init__(self, dimensions: int = 64, model_id: str = "fake-hashing"):
        if not 1 <= dimensions <= MAX_EMBEDDING_DIMENSIONS:
            raise ValueError("Invalid embedding provider configuration")
        self.dimensions = dimensions
        self.model_id = model_id

    def embed(self, texts: list[str]) -> dict:
        return {
            "model_id": self.model_id,
            "dimensions": self.dimensions,
            "vectors": [self._vector(text) for text in texts],
        }

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in text.lower().split() or ["<empty>"]:
            digest = hashlib.sha256(word.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
