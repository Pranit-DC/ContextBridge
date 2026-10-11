"""Synchronous dictionary boundaries permit independent module development.

Values must match the validation models exported by contextbridge.contracts. The engine
validates at the boundary; modules can use those models internally or keep their dict API.
"""

from typing import Any, Literal, Protocol

Message = dict[str, Any]


class Extractor(Protocol):
    def extract(self, event: Message) -> list[Message]: ...


class AdmissionPolicy(Protocol):
    def assess(self, candidate: Message, context: Message) -> Message: ...


class ResolutionPolicy(Protocol):
    def resolve(self, candidate: Message, context: Message) -> Message: ...


class Consolidator(Protocol):
    def propose(self, records: list[Message]) -> list[Message]: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> Message: ...


class RetrievalRepository(Protocol):
    def search_channel(
        self,
        channel: Literal["lexical", "semantic", "symbolic"],
        query: Message,
        query_embedding: Message | None,
        limit: int,
    ) -> list[Message]: ...

    def expand(self, version_ids: list[str], query: Message, limit: int) -> list[Message]: ...

    def inspect(self, memory_id: str, query: Message) -> Message: ...

    def is_live(self, version_id: str, query: Message) -> bool: ...


class Verifier(Protocol):
    def verify(self, record: Message, inspection: Message) -> Literal["supported", "uncertain"]: ...


class Retriever(Protocol):
    def search(
        self,
        query: Message,
        repository: RetrievalRepository,
        embedder: EmbeddingProvider,
        verifier: Verifier,
    ) -> Message: ...


class ViewerClient(Protocol):
    def search(self, query: Message) -> Message: ...

    def inspect(self, memory_id: str) -> Message: ...

    def correct(self, memory_id: str, update: Message) -> Message: ...

    def forget(self, memory_id: str) -> None: ...
