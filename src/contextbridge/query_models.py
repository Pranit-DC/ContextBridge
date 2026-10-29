"""Additive follow-up requests; common retrieval contract V1 remains unchanged."""

from uuid import UUID

from pydantic import Field

from contextbridge.contracts import RetrievalQuery
from contextbridge.schemas import StrictModel


class ReferencedQuery(StrictModel):
    memory_id: UUID
    expected_version: int = Field(ge=1, strict=True)
    query: RetrievalQuery
