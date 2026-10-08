from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Scope(StrEnum):
    DEVELOPER = "developer"
    PROJECT = "project"


class MemoryType(StrEnum):
    FACT = "FACT"
    DECISION = "DECISION"
    PREFERENCE = "PREFERENCE"
    STATE = "STATE"
    EVENT = "EVENT"
    LESSON = "LESSON"


class Source(StrictModel):
    kind: Annotated[str, StringConstraints(pattern=r"^(user|tool)$")]
    agent: Identifier
    session: Identifier
    interaction: Identifier
    evidence: Content


class ScopedRequest(StrictModel):
    scope: Scope
    project_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if (self.scope == Scope.PROJECT) != (self.project_id is not None):
            raise ValueError("Project scope requires project_id; developer scope forbids it")
        return self


class TemporalModel(StrictModel):
    valid_from: datetime | None = None

    @field_validator("valid_from")
    @classmethod
    def validate_time(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timestamp must include a timezone")
            value = value.astimezone(UTC)
            if value > datetime.now(UTC):
                raise ValueError("Future-effective writes are not supported by this milestone")
        return value


class CreateMemory(ScopedRequest, TemporalModel):
    request_id: UUID
    type: MemoryType
    content: Content
    source: Source
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)


class UpdateMemory(TemporalModel):
    expected_version: int = Field(ge=1)
    content: Content
    source: Source


class SearchMemories(ScopedRequest):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    include_developer: bool = False
    conditions: dict[Identifier, Identifier] = Field(default_factory=dict, max_length=20)
    as_of: datetime | None = None
    limit: int = Field(default=3, ge=1, le=20)

    @field_validator("as_of")
    @classmethod
    def validate_as_of(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timestamp must include a timezone")
            value = value.astimezone(UTC)
        return value


class VersionResponse(StrictModel):
    id: UUID
    number: int
    content: str
    status: str
    valid_from: datetime
    valid_to: datetime | None
    recorded_at: datetime
    source: Source

    @field_validator("valid_from", "valid_to", "recorded_at")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None


class MemoryResponse(StrictModel):
    id: UUID
    scope: Scope
    project_id: str | None
    type: MemoryType
    conditions: dict[str, str]
    created_at: datetime
    current_version: int
    version: VersionResponse

    @field_validator("created_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class EdgeResponse(StrictModel):
    from_version_id: UUID
    to_version_id: UUID
    relation: str


class InspectionResponse(StrictModel):
    memory: MemoryResponse
    history: list[VersionResponse]
    edges: list[EdgeResponse]
