"""Wire an injected retriever to the scoped store and verify returned stored fields."""

from datetime import UTC, datetime

from sqlalchemy import or_, select

from contextbridge.contracts import MemoryCard, RetrievalResult, SourceRef
from contextbridge.contracts.messages import MAX_RECORDS
from contextbridge.engine.conflict_ranking import ConflictRankingPolicy
from contextbridge.engine.context_budget import ContextBudget, bounded_warnings
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.query_understanding import understand
from contextbridge.models import MemoryEdge, MemoryVersion
from contextbridge.persistence.locks import lock_owner
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.security import contains_secret_fields


class ContextRepository(PostgresRepository):
    """Overfetch direct matches for ranking, but retain the caller's graph expansion bound.

    Expansion provenance is request-local policy state; common V1 cards remain unchanged.
    No related result may consume a direct match's slot or move ahead of direct context.
    """

    def __init__(self, *args, result_limit, **kwargs):
        super().__init__(*args, **kwargs)
        self.result_limit = result_limit
        self.expansion_seeds = None
        self.expanded_version_ids = set()

    def expand(self, version_ids, query, limit):
        limit = self.limit(limit)
        if not isinstance(version_ids, list) or len(version_ids) > MAX_RECORDS:
            raise EngineError("INVALID_INPUT", 422)
        ids = {self.uuid(value) for value in version_ids}
        if self.expansion_seeds is None:
            self.expansion_seeds = ids
        visited = self.expansion_seeds | self.expanded_version_ids
        slots = self.result_limit - len(visited)
        if slots <= 0:
            return []
        rows = super().expand(version_ids, query, min(limit, slots + len(visited), MAX_RECORDS))
        fresh = [row for row in rows if self.uuid(row["memory"]["version"]["id"]) not in visited][
            :slots
        ]
        self.expanded_version_ids.update(self.uuid(row["memory"]["version"]["id"]) for row in fresh)
        return fresh


class RetrievalService:
    def __init__(
        self,
        session,
        settings,
        modules,
        embedder=None,
        verifier=None,
        *,
        query_context=None,
        ranking_policy=None,
        context_budget=None,
    ):
        self.session, self.settings, self.modules = session, settings, modules
        self.embedder, self.verifier = embedder, verifier
        self.query_context = query_context
        self.ranking_policy = ranking_policy or ConflictRankingPolicy()
        self.context_budget = context_budget or ContextBudget()

    def search(self, query):
        if contains_secret_fields(query.model_dump(mode="json")):
            raise EngineError("INVALID_INPUT", 422)
        interpretation = understand(
            query, developer_id=self.settings.developer_id, context=self.query_context
        )
        if interpretation.needs_clarification:
            return RetrievalResult(
                schema_version=1, cards=[], degraded=False, warnings=list(interpretation.warnings)
            )
        query = query.model_copy(update={"as_of": query.as_of or datetime.now(UTC)})
        repository = ContextRepository(
            self.session,
            self.settings.developer_id,
            min_similarity=self.settings.retrieval_min_similarity,
            result_limit=query.limit,
        )
        query = repository.query(query.model_dump(mode="json"))
        try:
            pool_query = query.model_copy(
                update={"limit": min(self.ranking_policy.max_candidates, query.limit + 4)}
            )
            result = self.modules.search(pool_query, repository, self.embedder, self.verifier)
            lock_owner(self.session, self.settings.developer_id)
            rows = self.session.execute(
                repository.eligible(query).where(
                    MemoryVersion.id.in_([card.version_id for card in result.cards])
                )
            ).all()
            stored = {version.id: (memory, version) for memory, version in rows}
            for card in result.cards:
                row = stored.get(card.version_id)
                if row is None:
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
                memory, version = row
                actual = MemoryCard(
                    memory_id=memory.id,
                    version_id=version.id,
                    version_number=version.number,
                    type=memory.type,
                    content=version.content,
                    scope=memory.scope,
                    project_id=memory.project_id,
                    conditions=memory.conditions,
                    valid_from=version.valid_from,
                    valid_to=version.valid_to,
                    decision_state=version.decision_state,
                    verification=card.verification,
                    source_ref=SourceRef(
                        agent=version.source_agent,
                        session=version.source_session,
                        interaction=version.source_interaction,
                    ),
                )
                if actual != card:
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
            allowed = repository.eligible(query).with_only_columns(MemoryVersion.id)
            ids = [card.version_id for card in result.cards]
            edges = (
                self.session.execute(
                    select(MemoryEdge.from_version_id, MemoryEdge.to_version_id)
                    .where(
                        MemoryEdge.relation == "contradicts",
                        or_(MemoryEdge.from_version_id.in_(ids), MemoryEdge.to_version_id.in_(ids)),
                        MemoryEdge.from_version_id.in_(allowed),
                        MemoryEdge.to_version_id.in_(allowed),
                    )
                    .order_by(MemoryEdge.id)
                    .limit(self.ranking_policy.max_edges)
                ).all()
                if ids
                else []
            )
            cards, ranking_warnings = self.ranking_policy.rank(
                result.cards,
                edges,
                limit=max(1, len(result.cards)) if repository.expanded_version_ids else query.limit,
            )
            if repository.expanded_version_ids:
                cards.sort(key=lambda card: card.version_id in repository.expanded_version_ids)
                omitted = cards[query.limit :]
                cards = cards[: query.limit]
                disputed = {
                    card.version_id for card in result.cards if card.decision_state == "contested"
                }
                disputed.update(identifier for edge in edges for identifier in edge)
                if any(card.version_id in disputed for card in omitted):
                    ranking_warnings.append("CONFLICT_ALTERNATIVES_OMITTED")
            if len(edges) == self.ranking_policy.max_edges:
                ranking_warnings.append("CONFLICT_EDGE_LIMIT_REACHED")
            warnings = sorted(set(result.warnings) | repository.warnings | set(ranking_warnings))
            if len(warnings) > 20:
                warnings = bounded_warnings(
                    ranking_warnings + sorted(repository.warnings) + result.warnings
                )
            response = RetrievalResult(
                schema_version=1,
                cards=cards,
                degraded=result.degraded or bool(repository.warnings),
                warnings=warnings,
            )
            self.session.commit()
            response = self.context_budget.apply(response)
            # Pool expansion can be removed by reranking, the caller's limit or the
            # context budget. Describe only neighbors actually present in the output.
            related = repository.expanded_version_ids - repository.direct_version_ids
            if not any(card.version_id in related for card in response.cards):
                response = response.model_copy(
                    update={
                        "warnings": [
                            warning
                            for warning in response.warnings
                            if warning != "RELATED_MEMORIES_INCLUDED"
                        ]
                    }
                )
            return response
        except EngineError:
            raise
        except ModuleError as error:
            status = 422 if error.code == "INVALID_INPUT" else 503
            raise EngineError(error.code, status, retryable=error.retryable) from None
