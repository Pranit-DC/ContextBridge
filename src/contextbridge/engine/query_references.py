"""Resolve only a bounded topic from an explicitly selected, fresh scoped memory."""

import re
from datetime import UTC, datetime

from sqlalchemy import or_, select

from contextbridge.contracts import RetrievalQuery, RetrievalResult
from contextbridge.engine.errors import EngineError
from contextbridge.engine.query_understanding import (
    REFERENCE,
    TOPICS,
    AuthorizedQueryContext,
    understand,
)
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.models import Memory, MemoryEdge
from contextbridge.persistence.locks import lock_owner
from contextbridge.persistence.records import record_response
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.security import contains_secret_fields


def snapshot(session, settings, payload, query):
    repository = PostgresRepository(session, settings.developer_id)
    row = session.execute(repository.eligible(query).where(Memory.id == payload.memory_id)).first()
    if row is None:
        raise EngineError("OUT_OF_SCOPE", 404)
    stored, version = row
    if stored.scope != query.scope or stored.project_id != query.project_id:
        raise EngineError("OUT_OF_SCOPE", 404)
    if version.number != payload.expected_version:
        raise EngineError("VERSION_CONFLICT", 409)
    if payload.query.as_of is None and (
        stored.retired_at is not None or stored.current_version != payload.expected_version
    ):
        raise EngineError("VERSION_CONFLICT", 409)
    disputed = (
        session.scalar(
            select(MemoryEdge.id)
            .where(
                MemoryEdge.relation == "contradicts",
                or_(
                    MemoryEdge.from_version_id == version.id, MemoryEdge.to_version_id == version.id
                ),
            )
            .limit(1)
        )
        is not None
    )
    return record_response(stored, version).model_dump(mode="json"), stored.retired_at, disputed


def referenced_search(session, settings, modules, payload, *, embedder=None, verifier=None):
    if contains_secret_fields(payload.model_dump(mode="json")):
        raise EngineError("INVALID_INPUT", 422)
    query = payload.query.model_copy(update={"as_of": payload.query.as_of or datetime.now(UTC)})
    lock_owner(session, settings.developer_id)
    before = snapshot(session, settings, payload, query)
    memory = before[0]["memory"]
    topics = tuple(
        topic
        for topic, pattern in TOPICS.items()
        if re.search(pattern, memory["version"]["content"], re.I)
    )
    context = AuthorizedQueryContext(settings.developer_id, query.scope, query.project_id, topics)
    understanding = understand(payload.query, developer_id=settings.developer_id, context=context)
    warnings = list(understanding.warnings)
    matches = list(REFERENCE.finditer(query.query))
    if matches and (
        before[2]
        or before[0]["decision_state"] != "clear"
        or any(match[0].casefold() in {"the former", "the latter"} for match in matches)
    ):
        warnings.append("QUERY_REFERENCE_CLARIFICATION_REQUIRED")
    if warnings:
        session.commit()
        return RetrievalResult(
            schema_version=1, cards=[], degraded=False, warnings=sorted(set(warnings))
        )
    resolved = understanding.resolved_reference
    if resolved:
        rewritten = REFERENCE.sub(resolved, query.query)
        if len(rewritten) > 500:
            session.commit()
            return RetrievalResult(
                schema_version=1,
                cards=[],
                degraded=False,
                warnings=["QUERY_REFERENCE_REWRITE_LIMIT"],
            )
        query = RetrievalQuery.model_validate(query.model_dump() | {"query": rewritten})
    session.commit()  # Never hold the authorization lock during provider/quota waits.
    result = RetrievalService(session, settings, modules, embedder, verifier).search(query)
    lock_owner(session, settings.developer_id)
    if snapshot(session, settings, payload, query) != before:
        raise EngineError("VERSION_CONFLICT", 409)
    session.commit()
    return result
