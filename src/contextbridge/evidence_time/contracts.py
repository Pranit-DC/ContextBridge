from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, TypeAdapter, field_validator, model_validator

from contextbridge.contracts import CapturedEvent
from contextbridge.schemas import (
    Content,
    Identifier,
    MemoryResponse,
    MemoryType,
    ScopedRequest,
    SearchMemories,
    StrictModel,
)


class SourceEvent(CapturedEvent):
    source_timezone: Identifier

    @field_validator("occurred_at", mode="wrap")
    @classmethod
    def preserve_original_offset(cls, value, handler):
        handler(value)  # Retain common aware/past validation before preserving provenance.
        return TypeAdapter(AwareDatetime).validate_python(value)

    @field_validator("source_timezone")
    @classmethod
    def source_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValueError("Unknown source timezone") from None
        return value


class EvidenceBundle(StrictModel):
    schema_version: Literal[2]
    bundle_id: UUID
    events: list[SourceEvent] = Field(min_length=1, max_length=20)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 2:
            raise ValueError("Unsupported bundle version")
        return value

    @model_validator(mode="after")
    def bounded_group(self):
        first = self.events[0]
        if any(
            (e.scope, e.project_id, e.agent, e.session)
            != (first.scope, first.project_id, first.agent, first.session)
            for e in self.events
        ):
            raise ValueError("Bundle sources must share scope, project, agent and session")
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("Duplicate source event")
        if (
            sum(len(e.messages) for e in self.events) > 20
            or sum(len(m.content) for e in self.events for m in e.messages) > 32_000
        ):
            raise ValueError("Bundle exceeds capture bounds")
        if any(e.capture_method != "manual_import" for e in self.events):
            raise ValueError("Bundle source must be an explicit import")
        return self


class QuotedFragment(StrictModel):
    message_id: Identifier
    quote: Content


class Condition(StrictModel):
    key: Identifier
    value: Identifier


class BundleClaim(StrictModel):
    temporal_relation: Literal["state_transition", "event_occurrence", "context_only", "uncertain"]
    content: Content
    type: MemoryType
    conditions: list[Condition] = Field(max_length=20)
    claim_key: Identifier | None
    confidence: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    usefulness: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    evidence: list[QuotedFragment] = Field(min_length=1, max_length=20)


class BundleClaims(StrictModel):
    claims: list[BundleClaim] = Field(max_length=20)


class TemporalBounds(StrictModel):
    precision: Literal["instant", "day", "week", "range"]
    relation: Literal["state_transition", "event_occurrence", "context_only"]
    earliest: AwareDatetime
    latest: AwareDatetime
    guaranteed_from: AwareDatetime
    source_timezone: Identifier
    source_event_id: UUID
    normalized_evidence: Content

    @model_validator(mode="after")
    def ordered(self):
        if self.earliest > self.latest or (
            self.relation != "context_only"
            and not self.earliest <= self.guaranteed_from <= self.latest
        ):
            raise ValueError("Invalid temporal bounds")
        return self


class ProvenanceResult(StrictModel):
    memory_id: UUID
    version: int
    metadata: dict


class FragmentPointer(StrictModel):
    message_id: Identifier
    start: int = Field(ge=0, le=8000, strict=True)
    end: int = Field(ge=1, le=8000, strict=True)

    @model_validator(mode="after")
    def ordered(self):
        if self.start >= self.end:
            raise ValueError("Invalid evidence offsets")
        return self


class CandidateMetadata(StrictModel):
    schema_version: Literal[2] = 2
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    fragments: list[FragmentPointer] = Field(min_length=1, max_length=20)
    temporal: TemporalBounds


class ProvenanceQuery(ScopedRequest):
    memory_id: UUID
    version: int | None = Field(default=None, ge=1, strict=True)


class TemporalContextQuery(ScopedRequest):
    memory_id: UUID
    expected_version: int = Field(ge=1, strict=True)
    as_of: AwareDatetime
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)
    limit: int = Field(default=3, ge=1, le=3, strict=True)

    @field_validator("as_of")
    @classmethod
    def valid_time(cls, value):
        return SearchMemories.validate_as_of(value)


class TemporalItem(StrictModel):
    memory: MemoryResponse
    decision_state: Literal["clear", "contested"]
    role: Literal["possible_before", "possible_after", "applicable_at_time"]
    applicability: Literal["uncertain_transition", "applicable", "contested"]
    temporal: TemporalBounds | None


class TemporalContextResult(StrictModel):
    schema_version: Literal[2] = 2
    as_of: AwareDatetime
    items: list[TemporalItem] = Field(max_length=3)
    warnings: list[
        Literal[
            "TRANSITION_TIME_UNCERTAIN",
            "TEMPORAL_ALTERNATIVES_OMITTED",
            "NO_APPLICABLE_MEMORY",
            "CONTESTED_MEMORY",
        ]
    ] = Field(max_length=4)
