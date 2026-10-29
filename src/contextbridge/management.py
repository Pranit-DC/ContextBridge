"""Additive management HTTP messages; common module contract V1 stays unchanged."""

from datetime import datetime
from typing import Literal
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


class LifecycleState(StrictModel):
    retired_at: datetime | None
    current_version: int = Field(ge=1, strict=True)


class IndexingState(StrictModel):
    current_version: int = Field(ge=1, strict=True)
    status: Literal[
        "not_configured",
        "awaiting_worker",
        "retired",
        "queued",
        "running",
        "succeeded",
        "deferred",
        "failed",
        "cancelled",
    ]


class RuntimeState(StrictModel):
    capture_project_id: Identifier | None = None
    developer_capture_enabled: bool = Field(default=False, strict=True)
    extraction_configured: bool = Field(strict=True)
    consolidation_configured: bool = Field(strict=True)
    embeddings_configured: bool = Field(strict=True)
    default_context_limit: int = Field(default=3, ge=1, le=5, strict=True)
    viewer_context_limit: int = Field(default=5, ge=1, le=5, strict=True)
    provider_connection: Literal["not_probed"] = "not_probed"


class CompactionReference(StrictModel):
    memory_id: UUID
    expected_version: int = Field(ge=1, strict=True)


class CompactMemories(ScopedRequest):
    keep: CompactionReference
    retire: list[CompactionReference] = Field(min_length=1, max_length=19)
    confirm: bool = Field(default=False, strict=True)
    plan_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CompactionResult(StrictModel):
    applied: bool
    plan_revision: str
    kept_memory_id: UUID
    redundant_memory_ids: list[UUID] = Field(min_length=1, max_length=19)
    affected_memory_ids: list[UUID] = Field(min_length=1, max_length=200)
