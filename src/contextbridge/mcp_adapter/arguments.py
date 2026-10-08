from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from contextbridge.schemas import (
    Content,
    Identifier,
    MemoryType,
    Scope,
    SearchMemories,
    StrictModel,
    TemporalModel,
)


class Evidence(StrictModel):
    kind: Literal["user", "tool"]
    interaction: Identifier
    evidence: Content


class WriteArguments(TemporalModel):
    request_id: UUID
    type: MemoryType
    content: Content
    source: Evidence
    scope: Scope = Scope.PROJECT
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)


class SearchArguments(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    scope: Scope = Scope.PROJECT
    include_developer: bool = Field(default=False, strict=True)
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)
    as_of: datetime | None = None
    limit: int = Field(default=3, ge=1, le=5, strict=True)

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: datetime | None) -> datetime | None:
        return SearchMemories.validate_as_of(value)


class MemoryReference(StrictModel):
    memory_id: UUID


class UpdateArguments(TemporalModel, MemoryReference):
    expected_version: int = Field(ge=1, strict=True)
    content: Content
    source: Evidence


class NoArguments(StrictModel):
    pass
