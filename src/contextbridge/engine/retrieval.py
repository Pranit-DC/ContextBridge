"""Wire an injected retriever to the scoped store and verify returned stored fields."""

from datetime import UTC, datetime

from sqlalchemy import or_, select

from contextbridge.contracts import MemoryCard, RetrievalResult, SourceRef
from contextbridge.engine.conflict_ranking import ConflictRankingPolicy
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.query_understanding import understand
from contextbridge.models import MemoryEdge, MemoryVersion
from contextbridge.persistence.locks import lock_owner
from contextbridge.persistence.repository import PostgresRepository


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
    ):
        self.session, self.settings, self.modules = session, settings, modules
        self.embedder, self.verifier = embedder, verifier
        self.query_context = query_context
        self.ranking_policy = ranking_policy or ConflictRankingPolicy()

    def search(self, query):
        interpretation = understand(
            query, developer_id=self.settings.developer_id, context=self.query_context
        )
        if interpretation.needs_clarification:
            return RetrievalResult(
                schema_version=1, cards=[], degraded=False, warnings=list(interpretation.warnings)
            )
        query = query.model_copy(update={"as_of": query.as_of or datetime.now(UTC)})
        repository = PostgresRepository(
            self.session,
            self.settings.developer_id,
            min_similarity=self.settings.retrieval_min_similarity,
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
                result.cards, edges, limit=query.limit
            )
            if len(edges) == self.ranking_policy.max_edges:
                ranking_warnings.append("CONFLICT_EDGE_LIMIT_REACHED")
            warnings = sorted(set(result.warnings) | repository.warnings | set(ranking_warnings))
            if len(warnings) > 20:
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            response = RetrievalResult(
                schema_version=1,
                cards=cards,
                degraded=result.degraded or bool(repository.warnings),
                warnings=warnings,
            )
            self.session.commit()
            return response
        except EngineError:
            raise
        except ModuleError as error:
            status = 422 if error.code == "INVALID_INPUT" else 503
            raise EngineError(error.code, status, retryable=error.retryable) from None
