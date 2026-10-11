"""Deterministic test/demo substitutes, explicitly bound to recorded synthetic inputs."""

import copy
import hashlib
import json

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers import Support


def fingerprint(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class RecordedProvider:
    def __init__(self, event: dict, response: str):
        self._event = copy.deepcopy(event)
        self._response = response

    def generate(self, event: dict) -> str:
        if event != self._event:
            raise ModuleError("INVALID_INPUT")
        return self._response


class RecordedEvidenceVerifier:
    """Human-labelled support for exact event/candidate pairs; unknown pairs are uncertain."""

    def __init__(self, examples: list[tuple[dict, dict, Support]]):
        self._labels = {
            fingerprint([event, candidate]): verdict for event, candidate, verdict in examples
        }

    def verify(self, candidate: dict, event: dict) -> Support:
        return self._labels.get(fingerprint([event, candidate]), "uncertain")
