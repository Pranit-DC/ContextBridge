"""Exact synthetic substitutions for consolidation tests/demos, never a live default."""

import json

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers import Support
from contextbridge.formation.providers.recorded import fingerprint


def _ordered(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda r: r["memory"]["version"]["id"])


class RecordedGroupingProvider:
    def __init__(self, examples: list[tuple[list[dict], list[list[str]]]]):
        self._outputs = {
            fingerprint(_ordered(records)): json.dumps({"groups": groups})
            for records, groups in examples
        }

    def group(self, records: list[dict]) -> str:
        output = self._outputs.get(fingerprint(_ordered(records)))
        if output is None:
            raise ModuleError("INVALID_INPUT")
        return output


class RecordedConsolidationVerifier:
    """Design labels bind entire source snapshots; unknown input remains uncertain.

    The local consolidator constructs the summary from the exact source texts.
    Labels attest fixture support/compatibility only, not measured model accuracy.
    """

    def __init__(self, examples: list[tuple[list[dict], Support]]):
        self._labels = {fingerprint(_ordered(records)): label for records, label in examples}

    def verify(self, proposal: dict, records: list[dict]) -> Support:
        return self._labels.get(fingerprint(_ordered(records)), "uncertain")
