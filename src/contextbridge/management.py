"""Additive management HTTP messages; common module contract V1 stays unchanged."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from contextbridge.schemas import Identifier, MemoryResponse, ScopedRequest, Source, StrictModel


class RetireMemory(ScopedRequest):
    expected_version: int = Field(ge=1, strict=True)


class RestoreMemory(RetireMemory):
    source_version: int = Field(ge=1, strict=True)
    source: Source


class LifecycleResult(StrictModel):
    memory: MemoryResponse
    retired_at: datetime | None
    affected_memories: int = Field(ge=1, le=200)


class RetiredQuery(ScopedRequest):
    include_developer: bool = Field(default=False, strict=True)
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)
    cursor: UUID | None = None
    limit: int = Field(default=20, ge=1, le=100, strict=True)


class RetiredItem(StrictModel):
    memory: MemoryResponse
    retired_at: datetime


class RetiredResult(StrictModel):
    items: list[RetiredItem]
    next_cursor: UUID | None = None


class ConsolidationRequest(ScopedRequest):
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)
    version_ids: list[UUID] | None = Field(default=None, min_length=2, max_length=20)


class ConsolidationSubmission(StrictModel):
    status: str
    job_id: UUID | None = None
    work_id: UUID | None = None
    source_count: int = Field(ge=0, le=20)
