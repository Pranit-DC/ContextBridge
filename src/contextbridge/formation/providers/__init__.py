"""Injected provider interfaces; no model account, network client, or production fake default."""

import copy
from collections.abc import Callable
from typing import Literal, Protocol

from contextbridge.engine.errors import ModuleError

Support = Literal["supported", "unsupported", "uncertain"]


class ModelProvider(Protocol):
    def generate(self, event: dict) -> str:
        """Return a JSON list of complete contract-V1 candidates, or [] for filler."""
        ...


class EvidenceVerifier(Protocol):
    def verify(self, candidate: dict, event: dict) -> Support:
        """Check claim, type, conditions, time and scope against cited user/tool evidence.

        Unsupported suggestions, guesses and non-atomic claims are not supported.
        Unclear references, applicability or effective dates must be uncertain.
        """
        ...


def call[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ModuleError as exc:
        raise ModuleError(exc.code, retryable=exc.retryable) from None
    except (TimeoutError, ConnectionError):
        raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True) from None
    except Exception:
        raise ModuleError("INVALID_PROVIDER_OUTPUT") from None


def check_support(verifier: EvidenceVerifier, candidate: dict, event: dict) -> Support:
    result = call(lambda: verifier.verify(copy.deepcopy(candidate), copy.deepcopy(event)))
    if result not in ("supported", "unsupported", "uncertain"):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    return result
