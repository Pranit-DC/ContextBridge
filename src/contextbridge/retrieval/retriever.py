"""Hybrid retrieval over an injected repository; it owns no memory store of its own."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from contextbridge.contracts import (
    EmbeddingBatch,
    QueryEmbedding,
    RankedMatch,
    RetrievalQuery,
    RetrievalResult,
)
from contextbridge.contracts.interfaces import EmbeddingProvider, RetrievalRepository, Verifier
from contextbridge.engine.errors import ModuleError
from contextbridge.retrieval.expansion import MAX_HOPS, expand_related
from contextbridge.retrieval.fusion import CHANNELS, Fused, fuse, to_card
from contextbridge.security import contains_secret_fields

MAX_CHANNEL_LIMIT = 100


@dataclass(frozen=True)
class RetrievalConfig:
    """Tunable bounds. rrf_k damps the lead of top ranks; evaluate it before changing."""

    rrf_k: int = 60
    channel_limit: int = 50
    # The model/size the stored vectors were built with. When set, a query embedding from any
    # other model is never sent to the semantic channel; vectors from different models are
    # not comparable.
    embedding_model_id: str | None = None
    embedding_dimensions: int | None = None
    # Verification is selective: contested cards, cards whose record confidence is below
    # ``verify_below_confidence``, and any memory type listed in ``verify_types`` (opt-in for
    # high-impact types such as DECISION). At most ``max_verifications`` run per search.
    verify_below_confidence: float = 0.7
    verify_types: frozenset[str] = frozenset()
    max_verifications: int = 3
    # Off by default: related memories are added only to spare slots, after direct matches.
    expand_graph: bool = False
    max_hops: int = 1

    def __post_init__(self):
        if (
            not 1 <= self.max_hops <= MAX_HOPS
            or self.rrf_k < 1
            or not 1 <= self.channel_limit <= MAX_CHANNEL_LIMIT
            or (self.embedding_dimensions is not None and self.embedding_dimensions < 1)
            or not 0 <= self.verify_below_confidence <= 1
            or self.max_verifications < 0
        ):
            raise ValueError("Invalid retrieval configuration")


def normalize_query(payload: Any, now: datetime | None = None) -> RetrievalQuery:
    """Validate the caller's query and fix its time; scope, conditions, and limit stay as given.

    Only whitespace is normalized, so identifiers, paths, and punctuation survive. Nothing is
    inferred from the text: dates and environments the caller did not state are never added.
    """
    try:
        if contains_secret_fields(payload):
            raise ModuleError("INVALID_INPUT")
        query = RetrievalQuery.model_validate(payload)
    except (ValidationError, TypeError, ValueError, RecursionError):
        raise ModuleError("INVALID_INPUT") from None
    if contains_secret_fields(query.model_dump(mode="json")):
        raise ModuleError("INVALID_INPUT")
    # Resolve "now" once so every channel and the liveness check see the same instant.
    instant = query.as_of or now or datetime.now(UTC)
    return query.model_copy(update={"query": re.sub(r"\s+", " ", query.query), "as_of": instant})


class Retriever:
    def __init__(self, config: RetrievalConfig | None = None):
        self.config = config or RetrievalConfig()

    def search(
        self,
        query: dict,
        repository: RetrievalRepository,
        embedder: EmbeddingProvider,
        verifier: Verifier | None = None,
    ) -> dict:
        """Return at most ``query.limit`` cards.

        With a verifier, selected cards are checked against their inspected evidence and labelled
        ``supported`` or ``uncertain``; the others stay ``not_requested``. A label never removes
        a card: uncertainty is shown, not hidden."""
        request = normalize_query(query)
        instant = request.as_of
        wire = request.model_dump(mode="json")
        warnings: list[str] = []

        embedding = self._embed(embedder, request.query)
        if embedding is None:
            warnings.append("EMBEDDING_UNAVAILABLE")

        matches: list[RankedMatch] = []
        for channel in CHANNELS:
            if channel == "semantic" and embedding is None:
                continue
            payload = embedding.model_dump(mode="json") if channel == "semantic" else None
            try:
                raw = repository.search_channel(channel, wire, payload, self.config.channel_limit)
            except Exception:
                # The baseline channel failing means no honest answer; others degrade visibly.
                if channel == "lexical":
                    raise ModuleError("STORAGE_UNAVAILABLE", retryable=True) from None
                warnings.append(f"{channel.upper()}_UNAVAILABLE")
                continue
            valid, dropped = self._validated(raw, channel)
            matches.extend(valid)
            if dropped:
                warnings.append("INVALID_MATCHES_DROPPED")

        selected = []
        for item in fuse(matches, request, instant, rrf_k=self.config.rrf_k):
            if len(selected) >= request.limit:
                break
            try:
                live = repository.is_live(str(item.version_id), wire)
            except Exception:
                # Fail closed: an unverifiable record is never shown as current.
                warnings.append("LIVENESS_UNAVAILABLE")
                continue
            if live is True:
                selected.append(item)

        if self.config.expand_graph and selected and len(selected) < request.limit:
            related = expand_related(
                selected,
                repository,
                request,
                wire,
                slots=request.limit - len(selected),
                max_hops=self.config.max_hops,
                warnings=warnings,
            )
            if related:
                # Cards carry no "related" marker in contracts V1, so say so in the result.
                warnings.append("RELATED_MEMORIES_INCLUDED")
            selected.extend(related)

        verdicts = self._verify(selected, repository, verifier, wire, warnings)
        cards = [to_card(item, verdicts.get(item.version_id, "not_requested")) for item in selected]
        if not cards:
            warnings.append("NO_RESULTS")

        result = RetrievalResult(
            schema_version=1,
            cards=cards,
            degraded=any(w.endswith("_UNAVAILABLE") for w in warnings),
            warnings=list(dict.fromkeys(warnings)),
        )
        return result.model_dump(mode="json")

    def _needs_verification(self, item: Fused) -> bool:
        record, config = item.record, self.config
        return (
            record.decision_state == "contested"
            or record.memory.type in config.verify_types
            or (
                record.confidence is not None and record.confidence < config.verify_below_confidence
            )
        )

    def _verify(self, selected, repository, verifier, wire, warnings) -> dict:
        """Labels for the selected cards that warrant checking, bounded per search."""
        verdicts: dict = {}
        if verifier is None:
            return verdicts
        for item in selected:
            if not self._needs_verification(item):
                continue
            if len(verdicts) >= self.config.max_verifications:
                warnings.append("VERIFICATION_LIMIT_REACHED")
                break
            try:
                inspection = repository.inspect(str(item.record.memory.id), wire)
            except Exception:
                warnings.append("VERIFICATION_UNAVAILABLE")
                verdicts[item.version_id] = "uncertain"
                continue
            try:
                verdict = verifier.verify(item.record.model_dump(mode="json"), inspection)
            except Exception:
                verdict = "uncertain"
                warnings.append("VERIFICATION_UNAVAILABLE")
            if getattr(verifier, "unavailable", False) is True:
                warnings.append("VERIFICATION_UNAVAILABLE")
            # Anything but an explicit "supported" is shown as uncertain.
            verdicts[item.version_id] = "supported" if verdict == "supported" else "uncertain"
        return verdicts

    def _embed(self, embedder: EmbeddingProvider, text: str) -> QueryEmbedding | None:
        """Embedding failure degrades to lexical retrieval; it is never reported as semantic."""
        try:
            query_method = getattr(embedder, "embed_query", None)
            batch = EmbeddingBatch.model_validate(
                query_method(text) if callable(query_method) else embedder.embed([text])
            )
            if len(batch.vectors) != 1:
                return None
            config = self.config
            if config.embedding_model_id not in (None, batch.model_id):
                return None
            if config.embedding_dimensions not in (None, batch.dimensions):
                return None
            return QueryEmbedding(
                model_id=batch.model_id, dimensions=batch.dimensions, vector=batch.vectors[0]
            )
        except Exception:
            return None

    def _validated(self, raw: Any, channel: str) -> tuple[list[RankedMatch], bool]:
        valid, dropped = [], False
        if not isinstance(raw, list):
            return valid, True
        for entry in raw[: self.config.channel_limit]:
            try:
                match = RankedMatch.model_validate(entry)
            except (ValidationError, TypeError, ValueError):
                dropped = True
                continue
            if match.channel != channel:
                dropped = True
                continue
            valid.append(match)
        return valid, dropped
