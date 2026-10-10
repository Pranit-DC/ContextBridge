import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import case, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.schemas import (
    CreateMemory,
    EdgeResponse,
    InspectionResponse,
    MemoryResponse,
    Scope,
    SearchMemories,
    Source,
    UpdateMemory,
    VersionResponse,
)
from contextbridge.security import contains_secret


class MemoryServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def version_response(version: MemoryVersion) -> VersionResponse:
    return VersionResponse(
        id=version.id,
        number=version.number,
        content=version.content,
        status=version.status,
        valid_from=version.valid_from,
        valid_to=version.valid_to,
        recorded_at=version.recorded_at,
        source=Source(
            kind=version.source_kind,
            agent=version.source_agent,
            session=version.source_session,
            interaction=version.source_interaction,
            evidence=version.evidence,
        ),
    )


def memory_response(memory: Memory, version: MemoryVersion) -> MemoryResponse:
    return MemoryResponse(
        id=memory.id,
        scope=memory.scope,
        project_id=memory.project_id,
        type=memory.type,
        conditions=memory.conditions,
        created_at=memory.created_at,
        current_version=memory.current_version,
        version=version_response(version),
    )


def screen(payload: CreateMemory | UpdateMemory):
    def values(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield key
                if isinstance(item, str):
                    yield f"{key}={item}"
                yield from values(item)
        elif isinstance(value, list):
            for item in value:
                yield from values(item)

    # Inspect decoded fields; JSON escaping could hide credentials embedded in evidence.
    if any(contains_secret(value) for value in values(payload.model_dump(mode="json"))):
        raise MemoryServiceError(422, "Possible credential detected; remove it before saving")


def new_version(memory_id: UUID, number: int, payload, now: datetime) -> MemoryVersion:
    return MemoryVersion(
        id=uuid4(),
        memory_id=memory_id,
        number=number,
        content=payload.content,
        status="ACTIVE",
        valid_from=payload.valid_from or now,
        valid_to=None,
        recorded_at=now,
        source_kind=payload.source.kind,
        source_agent=payload.source.agent,
        source_session=payload.source.session,
        source_interaction=payload.source.interaction,
        evidence=payload.source.evidence,
    )


class MemoryService:
    def __init__(self, session: Session, developer_id: str):
        self.session = session
        self.developer_id = developer_id

    def get_memory(self, memory_id: UUID, *, lock: bool = False) -> Memory:
        stmt = select(Memory).where(
            Memory.id == memory_id, Memory.developer_id == self.developer_id
        )
        if lock:
            stmt = stmt.with_for_update()
        memory = self.session.scalar(stmt)
        if memory is None:
            raise MemoryServiceError(404, "Memory not found")
        return memory

    def create(self, payload: CreateMemory) -> MemoryResponse:
        screen(payload)
        canonical = json.dumps(
            payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        existing = self.session.scalar(
            select(Memory).where(
                Memory.developer_id == self.developer_id, Memory.request_id == payload.request_id
            )
        )
        if existing is not None:
            return self.replay_create(existing, fingerprint)
        now = datetime.now(UTC)
        memory = Memory(
            id=uuid4(),
            developer_id=self.developer_id,
            request_id=payload.request_id,
            request_fingerprint=fingerprint,
            scope=payload.scope.value,
            project_id=payload.project_id,
            type=payload.type.value,
            conditions=payload.conditions,
            created_at=now,
            current_version=1,
        )
        try:
            self.session.add(memory)
            self.session.flush()
            version = new_version(memory.id, 1, payload, now)
            self.session.add(version)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(Memory).where(
                    Memory.developer_id == self.developer_id,
                    Memory.request_id == payload.request_id,
                )
            )
            if existing is None:
                raise
            return self.replay_create(existing, fingerprint)
        return memory_response(memory, version)

    def replay_create(self, memory: Memory, fingerprint: str) -> MemoryResponse:
        if memory.request_fingerprint != fingerprint:
            raise MemoryServiceError(409, "request_id was already used for a different write")
        version = self.session.scalar(
            select(MemoryVersion).where(
                MemoryVersion.memory_id == memory.id, MemoryVersion.number == 1
            )
        )
        return memory_response(memory, version)

    def update(self, memory_id: UUID, payload: UpdateMemory) -> MemoryResponse:
        screen(payload)
        memory = self.get_memory(memory_id, lock=True)
        if memory.current_version != payload.expected_version:
            raise MemoryServiceError(
                409, "Memory changed; inspect it and retry with its current version"
            )
        previous = self.session.scalar(
            select(MemoryVersion).where(
                MemoryVersion.memory_id == memory.id,
                MemoryVersion.number == memory.current_version,
            )
        )
        now = datetime.now(UTC)
        effective = payload.valid_from or now
        if effective <= previous.valid_from:
            raise MemoryServiceError(
                422, "An update must take effect after the current version began"
            )
        previous.status = "SUPERSEDED"
        previous.valid_to = effective
        memory.current_version += 1
        version = new_version(memory.id, memory.current_version, payload, now)
        self.session.add(version)
        self.session.flush()
        self.session.add(
            MemoryEdge(
                id=uuid4(),
                from_version_id=version.id,
                to_version_id=previous.id,
                relation="supersedes",
            )
        )
        self.session.commit()
        return memory_response(memory, version)

    def inspect(self, memory_id: UUID) -> InspectionResponse:
        memory = self.get_memory(memory_id)
        versions = self.session.scalars(
            select(MemoryVersion)
            .where(MemoryVersion.memory_id == memory.id)
            .order_by(MemoryVersion.number)
        ).all()
        ids = [v.id for v in versions]
        edges = self.session.scalars(
            select(MemoryEdge).where(
                or_(MemoryEdge.from_version_id.in_(ids), MemoryEdge.to_version_id.in_(ids))
            )
        ).all()
        return InspectionResponse(
            memory=memory_response(memory, versions[-1]),
            history=[version_response(v) for v in versions],
            edges=[
                EdgeResponse(
                    from_version_id=e.from_version_id,
                    to_version_id=e.to_version_id,
                    relation=e.relation,
                )
                for e in edges
            ],
        )

    def forget(self, memory_id: UUID):
        memory = self.get_memory(memory_id, lock=True)
        self.session.delete(memory)
        self.session.commit()

    def search(self, payload: SearchMemories) -> list[MemoryResponse]:
        instant = payload.as_of or datetime.now(UTC)
        document = func.to_tsvector("english", MemoryVersion.content)
        query = func.plainto_tsquery("english", payload.query)
        lexical_match = document.op("@@")(query)
        # Full-text tokenization drops punctuation; literal matching preserves exact identifiers.
        literal_match = MemoryVersion.content.icontains(payload.query, autoescape=True)
        stmt = (
            select(Memory, MemoryVersion)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .where(
                Memory.developer_id == self.developer_id,
                MemoryVersion.valid_from <= instant,
                or_(MemoryVersion.valid_to.is_(None), MemoryVersion.valid_to > instant),
                or_(lexical_match, literal_match),
            )
        )
        project_match = (Memory.scope == Scope.PROJECT.value) & (
            Memory.project_id == payload.project_id
        )
        developer_match = Memory.scope == Scope.DEVELOPER.value
        if payload.scope == Scope.PROJECT:
            stmt = stmt.where(
                or_(project_match, developer_match) if payload.include_developer else project_match
            )
        else:
            stmt = stmt.where(developer_match)
        # All stored conditions must be satisfied; unconditional memories also qualify.
        stmt = stmt.where(cast(Memory.conditions, JSONB).contained_by(payload.conditions))
        rows = self.session.execute(
            stmt.order_by(
                case((project_match, 1), else_=0).desc(),
                func.ts_rank_cd(document, query).desc(),
                Memory.created_at.desc(),
                Memory.id,
            ).limit(payload.limit)
        )
        return [memory_response(memory, version) for memory, version in rows]
