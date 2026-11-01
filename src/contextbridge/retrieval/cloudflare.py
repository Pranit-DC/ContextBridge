"""Bounded hosted Qwen embeddings over Cloudflare's OpenAI-compatible endpoint."""

import json
import math
import re
from time import monotonic

import httpx

from contextbridge.engine.errors import ModuleError
from contextbridge.security import contains_secret

MODEL_ID = "@cf/qwen/qwen3-embedding-0.6b"
DIMENSIONS = 1024
QUERY_INSTRUCTION = (
    "Given a software development question, retrieve relevant developer and project memories "
    "that help answer the question."
)
# UTF-8 bounds are conservative for the hosted model's 8192-token context. Never truncate.
MAX_INPUT_BYTES = 8192
MAX_BATCH = 32
MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 2_097_152
BASE_URL_PATTERN = re.compile(
    r"https://api\.cloudflare\.com/client/v4/accounts/[0-9a-fA-F]{32}/ai/v1/?"
)


def valid_base_url(value: str) -> bool:
    return bool(BASE_URL_PATTERN.fullmatch(value))


class CloudflareEmbeddingBackend:
    """No SDK, local model, transport retries, redirects, or ambient proxy configuration.

    ``transport`` exists for synthetic tests. Production uses httpx's default TLS verification.
    Only static reason codes escape this boundary; response/error bodies are never exposed.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_id: str = MODEL_ID,
        dimensions: int = DIMENSIONS,
        timeout_seconds: float = 10,
        transport: httpx.BaseTransport | None = None,
    ):
        if (
            not isinstance(api_key, str)
            or not api_key.strip()
            or len(api_key) > 4096
            or any(c.isspace() for c in api_key)
            or not valid_base_url(base_url)
            or model_id != MODEL_ID
            or dimensions != DIMENSIONS
            or not 0 < timeout_seconds <= 120
        ):
            raise ValueError("Invalid Cloudflare embedding configuration")
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/embeddings"
        self.model_id, self.dimensions = model_id, dimensions
        self.timeout_seconds, self._transport = timeout_seconds, transport

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._request(texts)

    def embed_query_batch(self, texts: list[str]) -> list[list[float]]:
        self._check_input(texts)
        return self._request([f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text}" for text in texts])

    def _check_input(self, texts):
        if not isinstance(texts, list) or len(texts) > MAX_BATCH:
            raise ModuleError("INVALID_INPUT")
        for text in texts:
            try:
                valid = (
                    isinstance(text, str)
                    and bool(text.strip())
                    and len(text.encode("utf-8")) <= MAX_INPUT_BYTES
                    and not contains_secret(text)
                )
            except UnicodeError:
                valid = False
            if not valid:
                raise ModuleError("INVALID_INPUT")

    def _request(self, texts):
        self._check_input(texts)
        if not texts:
            return []
        body = json.dumps(
            {"model": self.model_id, "input": texts, "encoding_format": "float"},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise ModuleError("INVALID_INPUT")
        deadline = monotonic() + self.timeout_seconds
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=self.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    self._url,
                    content=body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                    },
                ) as response:
                    if response.status_code != 200:
                        raise ModuleError(
                            "EMBEDDING_UNAVAILABLE",
                            retryable=response.status_code in {408, 429}
                            or response.status_code >= 500,
                        )
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ModuleError("INVALID_PROVIDER_OUTPUT")
                    raw = bytearray()
                    for chunk in response.iter_bytes(chunk_size=16_384):
                        if monotonic() >= deadline:
                            raise ModuleError("EMBEDDING_UNAVAILABLE", retryable=True)
                        if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ModuleError("INVALID_PROVIDER_OUTPUT")
                        raw.extend(chunk)
            payload = json.loads(raw)
            return self._vectors(payload, len(texts))
        except ModuleError as error:
            raise ModuleError(error.code, retryable=error.retryable) from None
        except (ValueError, TypeError, RecursionError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
        except Exception:
            raise ModuleError("EMBEDDING_UNAVAILABLE", retryable=True) from None

    def _vectors(self, payload, expected):
        if not isinstance(payload, dict) or payload.get("model", self.model_id) != self.model_id:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        ordered = [None] * expected
        for item in data:
            if not isinstance(item, dict):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            index, vector = item.get("index"), item.get("embedding")
            if (
                type(index) is not int
                or not 0 <= index < expected
                or ordered[index] is not None
                or not isinstance(vector, list)
                or len(vector) != self.dimensions
                or any(
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or abs(value) > 3.4028234663852886e38  # PostgreSQL REAL storage
                    for value in vector
                )
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            ordered[index] = vector
        return ordered
