"""Validation for docs/team-plan/contracts-v1.md, separate from the existing API."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    Field,
    FiniteFloat,
    StringConstraints,
    field_validator,
    model_validator,
)

from contextbridge.schemas import (
    Content,
    Identifier,
    MemoryResponse,
    MemoryType,
    ScopedRequest,
    SearchMemories,
    Source,
    StrictModel,
)

Timestamp = Annotated[AwareDatetime, AfterValidator(lambda value: value.astimezone(UTC))]
Score = Annotated[FiniteFloat, Field(ge=0, le=1)]
ReasonCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
Conditions = Annotated[dict[Identifier, Identifier], Field(max_length=20)]
Channel = Literal["lexical", "semantic", "symbolic"]
DecisionState = Literal["clear", "contested"]
Verification = Literal["not_requested", "supported", "uncertain"]
MAX_CANDIDATES = 100
MAX_RECORDS = 200
MAX_EMBEDDING_DIMENSIONS = 4096


def require_past(value: datetime) -> datetime:
    if value > datetime.now(UTC):
        raise ValueError("Future-effective writes are not supported")
    return value


PastTimestamp = Annotated[Timestamp, AfterValidator(require_past)]


class VersionedMessage(StrictModel):
    schema_version: Literal[1]

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported contract version")
        return value


class CapturedMessage(StrictModel):
    message_id: Identifier
    role: Literal["user", "assistant", "tool"]
    content: Content


class CapturedEvent(VersionedMessage, ScopedRequest):
    event_id: UUID
    agent: Identifier
    session: Identifier
    interaction: Identifier
    occurred_at: PastTimestamp
    capture_method: Literal["manual_import", "verified_adapter"]
    messages: list[CapturedMessage] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_messages(self) -> Self:
        if sum(len(message.content) for message in self.messages) > 32_000:
            raise ValueError("Event content exceeds limit")
        ids = [message.message_id for message in self.messages]
        if len(ids) != len(set(ids)):
            raise ValueError("Message IDs must be unique within an event")
        return self


class EvidenceRef(StrictModel):
    event_id: UUID
    message_id: Identifier


class Candidate(VersionedMessage, ScopedRequest):
    candidate_id: UUID
    event_id: UUID
    type: MemoryType
    content: Content
    conditions: Conditions
    valid_from: PastTimestamp
    claim_key: Identifier | None
    confidence: Score
    usefulness: Score
    source: Source
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        refs = [(ref.event_id, ref.message_id) for ref in self.evidence_refs]
        if any(event_id != self.event_id for event_id, _ in refs):
            raise ValueError("Evidence must refer to the candidate event")
        if len(refs) != len(set(refs)):
            raise ValueError("Duplicate evidence reference")
        return self


class AdmissionDecision(VersionedMessage):
    candidate_id: UUID
    outcome: Literal["ADMIT", "REJECT", "DEFER"]
    reason_codes: list[ReasonCode] = Field(max_length=20)


class MemoryRecord(StrictModel):
    memory: MemoryResponse
    claim_key: Identifier | None
    confidence: Score | None
    decision_state: DecisionState


class ComparisonContext(VersionedMessage):
    checked_at: Timestamp
    records: list[MemoryRecord] = Field(max_length=MAX_RECORDS)


class WritePlan(VersionedMessage):
    candidate_id: UUID
    operation: Literal["CREATE", "UPDATE", "LINK_CONFLICT", "NOOP", "DEFER"]
    target_memory_id: UUID | None
    expected_version: int | None = Field(ge=1)
    reason_codes: list[ReasonCode] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.operation == "UPDATE" and (
            self.target_memory_id is None or self.expected_version is None
        ):
            raise ValueError("Updates require a target and expected version")
        if self.operation == "LINK_CONFLICT" and self.target_memory_id is None:
            raise ValueError("Conflicts require a target")
        if self.operation == "CREATE" and (
            self.target_memory_id is not None or self.expected_version is not None
        ):
            raise ValueError("Creates cannot replace a target")
        return self


class RetrievalQuery(VersionedMessage, SearchMemories):
    pass


class RankedMatch(StrictModel):
    record: MemoryRecord
    channel: Channel
    rank: int = Field(ge=1)


class QueryEmbedding(StrictModel):
    model_id: Identifier
    dimensions: int = Field(ge=1, le=MAX_EMBEDDING_DIMENSIONS)
    vector: list[FiniteFloat] = Field(min_length=1, max_length=MAX_EMBEDDING_DIMENSIONS)

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        if len(self.vector) != self.dimensions:
            raise ValueError("Embedding dimensions do not match")
        return self


class EmbeddingBatch(StrictModel):
    model_id: Identifier
    dimensions: int = Field(ge=1, le=MAX_EMBEDDING_DIMENSIONS)
    vectors: list[
        Annotated[list[FiniteFloat], Field(min_length=1, max_length=MAX_EMBEDDING_DIMENSIONS)]
    ] = Field(max_length=MAX_RECORDS)

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        if any(len(vector) != self.dimensions for vector in self.vectors):
            raise ValueError("Embedding dimensions do not match")
        return self


class SourceRef(StrictModel):
    agent: Identifier
    session: Identifier
    interaction: Identifier


class MemoryCard(ScopedRequest):
    memory_id: UUID
    version_id: UUID
    version_number: int = Field(ge=1)
    type: MemoryType
    content: Content
    conditions: Conditions
    valid_from: Timestamp
    valid_to: Timestamp | None
    decision_state: DecisionState
    verification: Verification
    source_ref: SourceRef

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("Invalid validity interval")
        return self


class RetrievalResult(VersionedMessage):
    cards: list[MemoryCard] = Field(max_length=20)
    degraded: bool
    warnings: list[ReasonCode] = Field(max_length=20)


class BrowseQuery(VersionedMessage, ScopedRequest):
    conditions: Conditions = Field(default_factory=dict)
    as_of: Timestamp | None = None
    limit: int = Field(default=20, ge=1, le=100)
    cursor: Annotated[str, StringConstraints(min_length=1, max_length=2048)] | None = None


class BrowseResult(VersionedMessage):
    items: list[MemoryRecord] = Field(max_length=100)
    next_cursor: Annotated[str, StringConstraints(min_length=1, max_length=2048)] | None


class ConsolidationProposal(VersionedMessage, ScopedRequest):
    proposal_id: UUID
    source_version_ids: list[UUID] = Field(min_length=1, max_length=MAX_RECORDS)
    summary: Content
    source_refs: list[SourceRef] = Field(min_length=1, max_length=MAX_RECORDS)
    conditions: Conditions


class IngestionResponse(VersionedMessage):
    event_id: UUID
    job_id: UUID
    status: Literal["accepted", "duplicate"]


class JobResponse(VersionedMessage):
    job_id: UUID
    event_id: UUID
    status: Literal["queued", "running", "succeeded", "deferred", "failed", "cancelled"]
    reason_codes: list[ReasonCode] = Field(max_length=20)
    memory_ids: list[UUID] = Field(max_length=MAX_CANDIDATES)
    updated_at: Timestamp
