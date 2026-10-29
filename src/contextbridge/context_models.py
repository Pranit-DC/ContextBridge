"""Additive opt-in context inspection; common V1 search messages stay unchanged."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from contextbridge.contracts import MemoryCard
from contextbridge.contracts.messages import Conditions, ScopedRequest, Timestamp
from contextbridge.schemas import StrictModel


class ContextQuery(ScopedRequest):
    memory_id: UUID
    expected_version: int | None = Field(default=None, ge=1, strict=True)
    conditions: Conditions = Field(default_factory=dict)
    as_of: Timestamp | None = None
    include_developer: bool = Field(default=False, strict=True)
    include_history: bool = Field(default=True, strict=True)
    verify_conflicts: bool = Field(default=False, strict=True)
    depth: int = Field(default=1, ge=1, le=3, strict=True)
    limit: int = Field(default=3, ge=1, le=10, strict=True)


class ContextItem(MemoryCard):
    role: Literal["seed", "historical", "conflicting"]
    relation: Literal["supersedes", "contradicts"] | None
    edge_source_version_id: UUID | None = None
    edge_target_version_id: UUID | None = None
    status: Literal["ACTIVE", "SUPERSEDED"]
    applicable_at_query: bool
    evidence_check: Literal[
        "not_requested", "supports", "contradicts", "insufficient", "unavailable"
    ] = "not_requested"
    content_omitted: bool = False


class ContextResult(StrictModel):
    as_of: Timestamp
    items: list[ContextItem] = Field(max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=20)
