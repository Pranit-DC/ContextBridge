"""Evidence-checked, extractive proposals; the shared engine owns live-source fencing."""

import copy
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, TypeAdapter, ValidationError

from contextbridge.contracts import ConsolidationProposal, MemoryRecord
from contextbridge.contracts.messages import MAX_RECORDS, Conditions, Timestamp
from contextbridge.engine.errors import ModuleError
from contextbridge.formation.extractor import invalid_constant, unique_object
from contextbridge.formation.providers import Support, call
from contextbridge.formation.providers.recorded import fingerprint
from contextbridge.schemas import (
    Content,
    Identifier,
    MemoryResponse,
    ScopedRequest,
    StrictModel,
    VersionResponse,
)
from contextbridge.security import contains_secret_fields

MAX_INPUT_CHARACTERS = 4_000_000
MAX_GROUPING_CHARACTERS = 32_000
MAX_PROPOSALS = 20
REVISION = "formation-extractive-consolidation-v1"


class GroupingProvider(Protocol):
    def group(self, records: list[dict]) -> str:
        """Return JSON {groups: [[version IDs], ...]} for one scope/condition bucket.

        Nonempty groups partition every input ID exactly once. Singletons retain
        unrelated facts without a summary; an empty groups list abstains entirely.
        """
        ...


class ConsolidationVerifier(Protocol):
    def verify(self, proposal: dict, records: list[dict]) -> Support:
        """Check relatedness, source support, compatible meaning/time and rare details.

        An evidence reference or identical claim key is not semantic proof. Guesses,
        contradictions and ambiguous applicability must never be supported.
        """
        ...


# Additional local input bounds do not change the common V1 dictionary contract.
class _Version(VersionResponse):
    number: Annotated[int, Field(strict=True, ge=1)]
    content: Content
    valid_from: Timestamp
    valid_to: Timestamp | None
    recorded_at: Timestamp


class _Memory(MemoryResponse):
    project_id: Identifier | None
    conditions: Conditions
    current_version: Annotated[int, Field(strict=True, ge=1)]
    created_at: Timestamp
    version: _Version


class _Record(MemoryRecord):
    memory: _Memory


class _Grouping(StrictModel):
    groups: list[Annotated[list[UUID], Field(min_length=1, max_length=MAX_RECORDS)]] = Field(
        max_length=MAX_RECORDS
    )


record_list = TypeAdapter(Annotated[list[_Record], Field(max_length=MAX_RECORDS)])


def _records(payload: list[dict]) -> list[dict]:
    try:
        if not isinstance(payload, list) or len(payload) > MAX_RECORDS:
            raise ValueError("Invalid record list")
        if contains_secret_fields(payload):
            raise ValueError("Sensitive input")
        raw = json.dumps(payload, allow_nan=False)
        if len(raw) > MAX_INPUT_CHARACTERS:
            raise ValueError("Input exceeds limit")
        records = record_list.validate_json(raw, strict=True)
        now = datetime.now(UTC)
        for record in records:
            memory, version = record.memory, record.memory.version
            ScopedRequest(scope=memory.scope, project_id=memory.project_id)
            if (
                memory.current_version != version.number
                or version.status != "ACTIVE"
                or version.valid_to is not None
                or max(version.valid_from, version.recorded_at, memory.created_at) > now
            ):
                raise ModuleError("VERSION_CONFLICT")
        result = [record.model_dump(mode="json") for record in records]
        if contains_secret_fields(result):
            raise ValueError("Sensitive normalized input")
        if len({r["memory"]["id"] for r in result}) != len(result) or len(
            {r["memory"]["version"]["id"] for r in result}
        ) != len(result):
            raise ValueError("Duplicate source")
        return sorted(result, key=lambda r: r["memory"]["version"]["id"])
    except (ValidationError, TypeError, ValueError, RecursionError):
        raise ModuleError("INVALID_INPUT") from None


def _groups(raw: str, records: list[dict]) -> list[list[dict]]:
    try:
        if not isinstance(raw, str) or len(raw) > MAX_GROUPING_CHARACTERS:
            raise ValueError("Invalid grouping output")
        decoded = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        if contains_secret_fields(decoded):
            raise ValueError("Sensitive grouping")
        groups = _Grouping.model_validate_json(raw, strict=True).groups
        by_id = {record["memory"]["version"]["id"]: record for record in records}
        ids = [str(version_id) for group in groups for version_id in group]
        if groups and (len(ids) != len(set(ids)) or set(ids) != set(by_id)):
            raise ValueError("Grouping must cover exactly the supplied versions")
        return sorted(
            [
                sorted([by_id[str(i)] for i in group], key=lambda r: r["memory"]["version"]["id"])
                for group in groups
            ],
            key=lambda group: group[0]["memory"]["version"]["id"],
        )
    except (ValidationError, TypeError, ValueError, KeyError, RecursionError):
        raise ModuleError("INVALID_PROVIDER_OUTPUT") from None


def _proposal(records: list[dict]) -> dict | None:
    # Preserve complete source text, including rare details, units and negation.
    # No model-generated summary is accepted in this fixture-stage implementation.
    memory = records[0]["memory"]
    facts = dict.fromkeys((r["memory"]["type"], r["memory"]["version"]["content"]) for r in records)
    summary = "\n".join(f"- [{kind}] {content}" for kind, content in facts)
    if len(summary) > 8000:
        return None  # Retain originals rather than truncate or discard a rare claim.
    refs = {
        tuple(r["memory"]["version"]["source"][key] for key in ("agent", "session", "interaction"))
        for r in records
    }
    return ConsolidationProposal(
        schema_version=1,
        proposal_id=uuid5(NAMESPACE_URL, f"{REVISION}:{fingerprint([records, summary])}"),
        source_version_ids=[r["memory"]["version"]["id"] for r in records],
        summary=summary,
        source_refs=[
            dict(zip(("agent", "session", "interaction"), ref, strict=True)) for ref in sorted(refs)
        ],
        scope=memory["scope"],
        project_id=memory["project_id"],
        conditions=memory["conditions"],
    ).model_dump(mode="json")


class Consolidator:
    def __init__(self, provider: GroupingProvider, verifier: ConsolidationVerifier):
        self.provider, self.verifier = provider, verifier

    def propose(self, records: list[dict]) -> list[dict]:
        checked = _records(records)
        buckets = defaultdict(list)
        for record in checked:
            memory = record["memory"]
            key = (
                memory["scope"],
                memory["project_id"],
                tuple(sorted(memory["conditions"].items())),
            )
            buckets[key].append(record)
        proposals = []
        for bucket in buckets.values():
            if len(bucket) < 2 or any(r["decision_state"] != "clear" for r in bucket):
                continue  # Leave contested/unrelated atomic records intact.
            raw = call(lambda bucket=bucket: self.provider.group(copy.deepcopy(bucket)))
            for group in _groups(raw, bucket):
                if len(group) < 2:
                    continue
                keyed_contents = defaultdict(set)
                for record in group:
                    if record["claim_key"] is not None:
                        keyed_contents[record["claim_key"]].add(
                            record["memory"]["version"]["content"]
                        )
                if any(len(contents) > 1 for contents in keyed_contents.values()):
                    continue  # Conservative abstention, not a declaration of contradiction.
                proposal = _proposal(group)
                if proposal is None:
                    continue
                support = call(
                    lambda proposal=proposal, group=group: self.verifier.verify(
                        copy.deepcopy(proposal), copy.deepcopy(group)
                    )
                )
                if support not in ("supported", "unsupported", "uncertain"):
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
                if support == "supported":
                    proposals.append(proposal)
        if len(proposals) > MAX_PROPOSALS:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return proposals
