"""Provider-independent extraction with bounded structured output and source grounding."""

import copy
import json
from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from contextbridge.contracts import Candidate
from contextbridge.contracts.messages import MAX_CANDIDATES
from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers import EvidenceVerifier, ModelProvider, call, check_support
from contextbridge.formation.validation import has_provenance, screened_event
from contextbridge.security import contains_secret_fields

MAX_OUTPUT_CHARACTERS = 2_000_000
candidate_list = TypeAdapter(Annotated[list[Candidate], Field(max_length=MAX_CANDIDATES)])


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value: str):
    raise ValueError("Non-finite JSON number")


class Extractor:
    def __init__(
        self, provider: ModelProvider, verifier: EvidenceVerifier, *, admission_checks=False
    ):
        self.provider = provider
        self.verifier = verifier
        self.admission_checks = admission_checks
        self.needs_confirmation = False

    def extract(self, event: dict) -> list[dict]:
        self.needs_confirmation = False
        captured = screened_event(event)
        payload = captured.model_dump(mode="json")
        if not any(message.role in ("user", "tool") for message in captured.messages):
            return []
        raw = call(lambda: self.provider.generate(captured.model_dump(mode="json")))
        self.needs_confirmation = (
            self.admission_checks
            and getattr(self.provider, "local_abstention", None) == "uncertain"
        )
        if not isinstance(raw, str) or len(raw) > MAX_OUTPUT_CHARACTERS:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        try:
            decoded = json.loads(
                raw, object_pairs_hook=unique_object, parse_constant=invalid_constant
            )
            if contains_secret_fields(decoded):
                raise ValueError("Sensitive output")
            candidates = candidate_list.validate_json(raw, strict=True)
        except (ValidationError, TypeError, ValueError, RecursionError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
        if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        proposals = []
        for candidate in candidates:
            if not has_provenance(candidate, captured):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            proposals.append(candidate.model_dump(mode="json"))
        prepare = (
            getattr(self.verifier, "prepare", None)
            if getattr(self.verifier, "formation_batch_verification", False) is True
            else None
        )
        if prepare is not None:
            call(lambda: prepare(copy.deepcopy(proposals), copy.deepcopy(payload)))
        for proposal in proposals:
            if (
                check_support(self.verifier, proposal, payload) != "supported"
                and not self.admission_checks
            ):
                # Distinguish unsupported/uncertain output from a genuine empty extraction.
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return proposals
