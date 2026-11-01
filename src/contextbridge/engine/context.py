"""Opt-in historical context and selective conflicting-evidence checks."""

from datetime import UTC, datetime

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from contextbridge.context_models import ContextItem, ContextResult
from contextbridge.contracts import RetrievalQuery, SourceRef
from contextbridge.engine.context_budget import encoded_size
from contextbridge.engine.errors import EngineError
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.persistence.locks import lock_owner
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.security import contains_secret_fields

MAX_CHECKS = 4
MAX_BYTES = 12_000


def item(memory, version, role, relation=None, edge=None):
    return ContextItem(
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
        verification="uncertain"
        if version.decision_state == "contested" or role == "conflicting"
        else "not_requested",
        source_ref=SourceRef(
            agent=version.source_agent,
            session=version.source_session,
            interaction=version.source_interaction,
        ),
        role=role,
        relation=relation,
        edge_source_version_id=edge.from_version_id if edge is not None else None,
        edge_target_version_id=edge.to_version_id if edge is not None else None,
        status=version.status,
        applicable_at_query=role != "historical",
    )


class MemoryContextService:
    def __init__(self, session, settings, verifier=None):
        self.session, self.settings = session, settings
        self.judge = getattr(verifier, "judge", None)

    def snapshot(self, query):
        """Read only authorized endpoints; never use unfiltered inspection for traversal."""
        repository = PostgresRepository(self.session, self.settings.developer_id)
        request = RetrievalQuery(
            schema_version=1,
            scope=query.scope,
            project_id=query.project_id,
            include_developer=query.include_developer,
            conditions=query.conditions,
            as_of=query.as_of,
            query="context",
            limit=1,
        )
        seed = self.session.execute(
            repository.eligible(request).where(Memory.id == query.memory_id).limit(2)
        ).all()
        if not seed:
            raise EngineError("OUT_OF_SCOPE", 404)
        if len(seed) != 1:
            raise EngineError("VERSION_CONFLICT", 409)
        memory, version = seed[0]
        if query.expected_version is not None and query.expected_version != version.number:
            raise EngineError("VERSION_CONFLICT", 409)
        result, sources, edges, warnings = [item(memory, version, "seed")], {}, set(), []

        def remember(m, v):
            sources[v.id] = (
                v.content,
                v.evidence,
                v.source_kind,
                v.source_agent,
                v.source_session,
                v.source_interaction,
            )

        remember(memory, version)
        allowed = (
            repository.eligible(request)
            .where(
                Memory.scope == memory.scope,
                Memory.project_id == memory.project_id,
                cast(Memory.conditions, JSONB) == memory.conditions,
            )
            .with_only_columns(MemoryVersion.id)
        )
        relations = self.session.scalars(
            select(MemoryEdge)
            .where(
                MemoryEdge.relation == "contradicts",
                or_(
                    MemoryEdge.from_version_id == version.id, MemoryEdge.to_version_id == version.id
                ),
                MemoryEdge.from_version_id.in_(allowed),
                MemoryEdge.to_version_id.in_(allowed),
            )
            .order_by(MemoryEdge.id)
            .limit(query.limit + 1)
        ).all()
        peer_edges = {}
        for edge in relations:
            peer = (
                edge.to_version_id if edge.from_version_id == version.id else edge.from_version_id
            )
            peer_edges[peer] = edge
        peers = self.session.execute(
            repository.eligible(request)
            .where(MemoryVersion.id.in_(peer_edges))
            .order_by(MemoryVersion.id)
            .limit(query.limit)
        ).all()
        for peer_memory, peer in peers:
            if peer_memory.conditions != memory.conditions:
                continue
            if len(result) >= query.limit:
                warnings.append("CONFLICT_CONTEXT_OMITTED")
                break
            result.append(
                item(peer_memory, peer, "conflicting", "contradicts", peer_edges[peer.id])
            )
            remember(peer_memory, peer)
            edges.add(peer_edges[peer.id].id)
        if len(relations) == query.limit + 1:
            warnings.append("CONFLICT_CONTEXT_OMITTED")
        if relations:
            result[0] = result[0].model_copy(update={"verification": "uncertain"})

        frontier, seen = {version.id: version}, {version.id}
        if query.include_history:
            for _ in range(query.depth):
                rows = self.session.execute(
                    select(MemoryVersion, MemoryEdge)
                    .join(MemoryEdge, MemoryEdge.to_version_id == MemoryVersion.id)
                    .where(
                        MemoryVersion.memory_id == memory.id,
                        MemoryVersion.status == "SUPERSEDED",
                        MemoryVersion.valid_to <= query.as_of,
                        MemoryEdge.relation == "supersedes",
                        MemoryEdge.from_version_id.in_(frontier),
                    )
                    .order_by(MemoryVersion.number.desc())
                    .limit(query.limit + 1)
                    .execution_options(populate_existing=True)
                ).all()
                following = {}
                for old, edge in rows:
                    parent = frontier[edge.from_version_id]
                    if (
                        old.id in seen
                        or old.number >= parent.number
                        or old.valid_to > parent.valid_from
                    ):
                        continue
                    if len(result) >= query.limit:
                        warnings.append("HISTORICAL_CONTEXT_OMITTED")
                        break
                    seen.add(old.id)
                    following[old.id] = old
                    result.append(item(memory, old, "historical", "supersedes", edge))
                    remember(memory, old)
                    edges.add(edge.id)
                frontier = following
                if not frontier:
                    break
        if contains_secret_fields([i.model_dump(mode="json") for i in result]) or any(
            contains_secret_fields({"content": value[0], "evidence": value[1]})
            for value in sources.values()
        ):
            raise EngineError("INVALID_PROVIDER_OUTPUT", 503)
        return result, sources, edges, sorted(set(warnings))

    def revalidate(self, query, snapshot):
        lock_owner(self.session, self.settings.developer_id)
        self.session.expire_all()
        if self.snapshot(query) != snapshot:
            raise EngineError("VERSION_CONFLICT", 409)
        self.session.commit()

    @staticmethod
    def compact(as_of, items, warnings, *, max_bytes=MAX_BYTES):
        response = ContextResult(as_of=as_of, items=items, warnings=sorted(set(warnings)))
        response.items = [
            entry.model_copy(
                update={
                    "content": (
                        f"[Full claim omitted; inspect memory {entry.memory_id}, "
                        f"version {entry.version_number}.]"
                    ),
                    "content_omitted": True,
                }
            )
            if len(entry.content) > 1500
            else entry
            for entry in response.items
        ]
        if any(entry.content_omitted for entry in response.items):
            response.warnings.append("CONTEXT_CONTENT_OMITTED")
        while encoded_size(response) > max_bytes and len(response.items) > 1:
            omitted = response.items.pop()
            response.warnings.extend(
                [
                    "CONTEXT_ITEMS_OMITTED",
                    "CONFLICT_CONTEXT_OMITTED"
                    if omitted.role == "conflicting"
                    else "HISTORICAL_CONTEXT_OMITTED",
                ]
            )
            response.warnings = sorted(set(response.warnings))
        if encoded_size(response) > max_bytes:
            raise EngineError("INVALID_PROVIDER_OUTPUT", 503)
        response.warnings = sorted(set(response.warnings))
        return response

    def inspect(self, query):
        if contains_secret_fields(query.model_dump(mode="json")):
            raise EngineError("INVALID_INPUT", 422)
        query = query.model_copy(update={"as_of": query.as_of or datetime.now(UTC)})
        lock_owner(self.session, self.settings.developer_id)
        snapshot = self.snapshot(query)
        self.session.commit()  # Never hold owner locks while a provider is running.
        items, sources, _, _ = snapshot
        # Reserve space for verification warnings before paying to check any evidence.
        response = self.compact(query.as_of, items, snapshot[3], max_bytes=MAX_BYTES - 256)
        warnings = list(response.warnings)
        checked = {}
        conflicts = [entry for entry in response.items if entry.role == "conflicting"]
        if query.verify_conflicts and conflicts:

            def guard():
                self.revalidate(query, snapshot)

            binder = getattr(self.judge, "bind_guard", None)
            previous = binder(guard) if callable(binder) else None
            try:
                for entry in [items[0], *conflicts]:
                    if len(checked) >= MAX_CHECKS:
                        warnings.append("VERIFICATION_LIMIT_REACHED")
                        break
                    if self.judge is None:
                        checked[entry.version_id] = "unavailable"
                        warnings.append("VERIFICATION_UNAVAILABLE")
                        break
                    guard()  # Also fence simple injected/local judges without quota hooks.
                    try:
                        claim, evidence, *_ = sources[entry.version_id]
                        verdict = self.judge.judge(claim, evidence)
                        if verdict not in {"supports", "contradicts", "insufficient"}:
                            raise ValueError
                    except Exception:
                        checked[entry.version_id] = "unavailable"
                        warnings.append("VERIFICATION_UNAVAILABLE")
                        break  # No additional requests after the first provider failure.
                    checked[entry.version_id] = verdict
            finally:
                if callable(binder):
                    binder(previous)
        self.revalidate(query, snapshot)
        return self.compact(
            query.as_of,
            [
                entry.model_copy(
                    update={"evidence_check": checked.get(entry.version_id, "not_requested")}
                )
                for entry in response.items
            ],
            warnings,
        )
