"""The agreed retrieval repository backed by the single authorized PostgreSQL store."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import bindparam, cast, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, REAL

from contextbridge.contracts import QueryEmbedding, RankedMatch, RetrievalQuery
from contextbridge.contracts.messages import MAX_RECORDS
from contextbridge.engine.errors import EngineError
from contextbridge.models import EmbeddingModel, Memory, MemoryEdge, MemoryEmbedding, MemoryVersion
from contextbridge.persistence.records import record_response
from contextbridge.persistence.vectors import VectorSQL, vector32, vector_available
from contextbridge.schemas import EdgeResponse, InspectionResponse, Scope
from contextbridge.security import contains_secret_fields
from contextbridge.service import memory_response, version_response


class PostgresRepository:
    def __init__(self, session, developer_id, *, min_similarity=0.4):
        self.session = session
        self.developer_id = developer_id
        self.instant = datetime.now(UTC)
        self.warnings = set()
        self.direct_version_ids = set()
        self.expanded_version_ids = set()
        self.min_similarity = min_similarity

    def query(self, raw):
        try:
            query = RetrievalQuery.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            raise EngineError("INVALID_INPUT", 422) from None
        if contains_secret_fields(query.model_dump(mode="json")):
            raise EngineError("INVALID_INPUT", 422)
        return query.model_copy(update={"as_of": query.as_of or self.instant})

    def limit(self, value):
        if type(value) is not int or not 1 <= value <= MAX_RECORDS:
            raise EngineError("INVALID_INPUT", 422)
        return value

    def uuid(self, value):
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            raise EngineError("INVALID_INPUT", 422) from None

    def eligible(self, query):
        scope = Memory.scope == Scope.DEVELOPER
        if query.scope == Scope.PROJECT:
            project = (Memory.scope == Scope.PROJECT) & (Memory.project_id == query.project_id)
            scope = or_(project, scope) if query.include_developer else project
        return (
            select(Memory, MemoryVersion)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .where(
                Memory.developer_id == self.developer_id,
                scope,
                cast(Memory.conditions, JSONB).contained_by(query.conditions),
                MemoryVersion.valid_from <= query.as_of,
                or_(MemoryVersion.valid_to.is_(None), MemoryVersion.valid_to > query.as_of),
            )
            .execution_options(populate_existing=True)
        )

    def search_channel(self, channel, query, query_embedding, limit):
        query, limit = self.query(query), self.limit(limit)
        stmt = self.eligible(query)
        if channel == "lexical":
            document = func.to_tsvector("english", MemoryVersion.content)
            terms = func.plainto_tsquery("english", query.query)
            stmt = stmt.where(document.op("@@")(terms)).order_by(
                func.ts_rank_cd(document, terms).desc(), Memory.id
            )
        elif channel == "symbolic":
            stmt = stmt.where(
                or_(
                    MemoryVersion.content.icontains(query.query, autoescape=True),
                    Memory.claim_key.icontains(query.query, autoescape=True),
                )
            ).order_by(Memory.id)
        elif channel == "semantic":
            if query_embedding is None:
                self.warnings.add("EMBEDDING_UNAVAILABLE")
                return []
            try:
                embedding = QueryEmbedding.model_validate(query_embedding)
            except (ValidationError, TypeError, ValueError):
                raise EngineError("INVALID_INPUT", 422) from None
            vector = vector32(embedding.vector)
            if contains_secret_fields(embedding.model_dump(mode="json")):
                raise EngineError("INVALID_INPUT", 422)
            model = self.session.get(EmbeddingModel, (self.developer_id, embedding.model_id))
            if model is not None and model.dimensions != embedding.dimensions:
                raise EngineError("INVALID_INPUT", 422)
            if model is None or not vector_available(self.session):
                self.warnings.add("EMBEDDING_UNAVAILABLE")
                return []
            digest = func.encode(func.sha256(func.convert_to(MemoryVersion.content, "UTF8")), "hex")
            indexed_filters = (
                MemoryEmbedding.version_id == MemoryVersion.id,
                MemoryEmbedding.developer_id == self.developer_id,
                MemoryEmbedding.model_id == embedding.model_id,
                MemoryEmbedding.dimensions == embedding.dimensions,
                MemoryEmbedding.content_fingerprint == digest,
            )
            indexed = select(MemoryEmbedding.version_id).where(*indexed_filters).exists()
            if self.session.scalar(
                stmt.with_only_columns(MemoryVersion.id).where(~indexed).limit(1)
            ):
                self.warnings.add("EMBEDDING_UNAVAILABLE")
            matching = (
                self.eligible(query)
                .join(MemoryEmbedding, MemoryEmbedding.version_id == MemoryVersion.id)
                .where(*indexed_filters)
            )
            parameter = bindparam("query_vector", value=vector, type_=ARRAY(REAL))
            distance = cast(MemoryEmbedding.vector, VectorSQL()).op("<=>")(
                cast(parameter, VectorSQL())
            )
            # Nearest does not mean relevant: with one stored memory, an unbounded
            # nearest-neighbour query otherwise returns it for every possible question.
            # Filter before LIMIT so weak matches cannot fill the result cards.
            stmt = matching.where(distance <= 1 - self.min_similarity).order_by(distance, Memory.id)
        else:
            raise EngineError("INVALID_INPUT", 422)
        rows = self.session.execute(stmt.limit(limit)).all()
        self.direct_version_ids.update(version.id for _, version in rows)
        return [
            RankedMatch(record=record_response(*row), channel=channel, rank=rank).model_dump(
                mode="json"
            )
            for rank, row in enumerate(rows, 1)
        ]

    def is_live(self, version_id, query):
        query = self.query(query)
        return (
            self.session.scalar(
                self.eligible(query)
                .with_only_columns(MemoryVersion.id)
                .where(MemoryVersion.id == self.uuid(version_id))
            )
            is not None
        )

    def inspect(self, memory_id, query):
        query = self.query(query)
        row = self.session.execute(
            self.eligible(query).where(Memory.id == self.uuid(memory_id))
        ).first()
        if row is None:
            raise EngineError("OUT_OF_SCOPE", 404)
        memory, version = row
        history = self.session.scalars(
            select(MemoryVersion)
            .where(MemoryVersion.memory_id == memory.id, MemoryVersion.valid_from <= query.as_of)
            .order_by(MemoryVersion.number)
            .limit(MAX_RECORDS + 1)
        ).all()
        if len(history) > MAX_RECORDS:
            raise EngineError("INVALID_INPUT", 422)
        allowed = self.eligible(query).with_only_columns(MemoryVersion.id)
        edges = self.session.scalars(
            select(MemoryEdge)
            .where(
                or_(
                    MemoryEdge.from_version_id == version.id, MemoryEdge.to_version_id == version.id
                ),
                MemoryEdge.from_version_id.in_(allowed),
                MemoryEdge.to_version_id.in_(allowed),
            )
            .order_by(MemoryEdge.id)
            .limit(MAX_RECORDS)
        ).all()
        return InspectionResponse(
            memory=memory_response(memory, version),
            history=[version_response(v) for v in history],
            edges=[
                EdgeResponse(
                    from_version_id=e.from_version_id,
                    to_version_id=e.to_version_id,
                    relation=e.relation,
                )
                for e in edges
            ],
        ).model_dump(mode="json")

    def expand(self, version_ids, query, limit):
        """Return eligible one-hop neighbors; the retriever owns traversal depth."""
        query, limit = self.query(query), self.limit(limit)
        if not isinstance(version_ids, list) or len(version_ids) > MAX_RECORDS:
            raise EngineError("INVALID_INPUT", 422)
        seeds = {self.uuid(value) for value in version_ids}
        if not seeds:
            return []
        allowed = self.eligible(query).with_only_columns(MemoryVersion.id)
        authorized = set(self.session.scalars(allowed.where(MemoryVersion.id.in_(seeds))))
        if authorized != seeds:
            raise EngineError("OUT_OF_SCOPE", 404)
        edges = self.session.execute(
            select(MemoryEdge.from_version_id, MemoryEdge.to_version_id)
            .where(
                or_(
                    MemoryEdge.from_version_id.in_(seeds),
                    MemoryEdge.to_version_id.in_(seeds),
                ),
                MemoryEdge.from_version_id.in_(allowed),
                MemoryEdge.to_version_id.in_(allowed),
            )
            .order_by(MemoryEdge.id)
            .limit(MAX_RECORDS)
        ).all()
        neighbors = {value for edge in edges for value in edge} - seeds
        neighbors = sorted(neighbors)[: MAX_RECORDS - len(seeds)]
        rows = self.session.execute(
            self.eligible(query)
            .where(MemoryVersion.id.in_(neighbors))
            .order_by(Memory.id)
            .limit(limit)
        ).all()
        self.expanded_version_ids.update(version.id for _, version in rows)
        return [record_response(*row).model_dump(mode="json") for row in rows]
