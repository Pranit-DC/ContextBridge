"""Injected module calls, with no persistence, scheduling, or fake production providers."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from pydantic import Field, TypeAdapter, ValidationError

from contextbridge.contracts import Candidate, CapturedEvent, RetrievalQuery, RetrievalResult
from contextbridge.contracts.interfaces import (
    AdmissionPolicy,
    Consolidator,
    EmbeddingProvider,
    Extractor,
    ResolutionPolicy,
    RetrievalRepository,
    Retriever,
    Verifier,
)
from contextbridge.contracts.messages import MAX_CANDIDATES
from contextbridge.engine.errors import ModuleError
from contextbridge.schemas import Scope
from contextbridge.security import contains_secret_fields

candidate_list = TypeAdapter(Annotated[list[Candidate], Field(max_length=MAX_CANDIDATES)])


def call_provider[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ModuleError as exc:
        # Rebuild safe errors even when an implementation mutated exception attributes.
        raise ModuleError(exc.code, retryable=exc.retryable) from None
    except (TimeoutError, ConnectionError):
        raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True) from None
    except Exception:
        raise ModuleError("INVALID_PROVIDER_OUTPUT") from None


@dataclass(frozen=True)
class ModuleGateway:
    extractor: Extractor | None = None
    admission: AdmissionPolicy | None = None
    resolution: ResolutionPolicy | None = None
    consolidator: Consolidator | None = None
    retriever: Retriever | None = None

    def extract(self, event: CapturedEvent) -> list[Candidate]:
        payload = event.model_dump(mode="json")
        if contains_secret_fields(payload):
            raise ModuleError("INVALID_INPUT")
        if self.extractor is None:
            raise ModuleError("PROVIDER_UNAVAILABLE")
        raw = call_provider(lambda: self.extractor.extract(payload))
        try:
            candidates = candidate_list.validate_python(raw)
        except (ValidationError, TypeError, ValueError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
        if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        messages = {message.message_id: message for message in event.messages}
        for candidate in candidates:
            if (
                candidate.event_id != event.event_id
                or candidate.scope != event.scope
                or candidate.project_id != event.project_id
                or candidate.source.agent != event.agent
                or candidate.source.session != event.session
                or candidate.source.interaction != event.interaction
                or contains_secret_fields(candidate.model_dump(mode="json"))
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            referenced = [messages.get(ref.message_id) for ref in candidate.evidence_refs]
            if any(message is None or message.role == "assistant" for message in referenced):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            if not any(
                message.role == candidate.source.kind
                and candidate.source.evidence in message.content
                for message in referenced
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        # Matching an excerpt establishes provenance, not semantic support or admission.
        return candidates

    def search(
        self,
        query: RetrievalQuery,
        repository: RetrievalRepository,
        embedder: EmbeddingProvider,
        verifier: Verifier,
    ) -> RetrievalResult:
        if self.retriever is None:
            raise ModuleError("PROVIDER_UNAVAILABLE")
        instant = query.as_of or datetime.now(UTC)
        query = query.model_copy(update={"as_of": instant})
        payload = query.model_dump(mode="json")
        if contains_secret_fields(payload):
            raise ModuleError("INVALID_INPUT")
        raw = call_provider(lambda: self.retriever.search(payload, repository, embedder, verifier))
        try:
            result = RetrievalResult.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
        if len(result.cards) > query.limit or len(
            {card.version_id for card in result.cards}
        ) != len(result.cards):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        for card in result.cards:
            scope_matches = (
                card.scope == Scope.DEVELOPER
                and (query.scope == Scope.DEVELOPER or query.include_developer)
            ) or (
                query.scope == Scope.PROJECT
                and card.scope == Scope.PROJECT
                and card.project_id == query.project_id
            )
            if (
                not scope_matches
                or not card.conditions.items() <= query.conditions.items()
                or card.valid_from > instant
                or (card.valid_to is not None and card.valid_to <= instant)
                or contains_secret_fields(card.model_dump(mode="json"))
                or not call_provider(
                    lambda card=card: repository.is_live(str(card.version_id), payload)
                )
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return result
