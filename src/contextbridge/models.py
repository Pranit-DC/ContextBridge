from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        UniqueConstraint("developer_id", "request_id", name="uq_memory_write_request"),
        CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_memory_scope",
        ),
        CheckConstraint(
            "type IN ('FACT', 'DECISION', 'PREFERENCE', 'STATE', 'EVENT', 'LESSON')",
            name="ck_memory_type",
        ),
        Index("ix_memory_owner_scope", "developer_id", "scope", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[UUID] = mapped_column()
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[str | None] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(16))
    conditions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_version: Mapped[int] = mapped_column(Integer)


class MemoryVersion(Base):
    __tablename__ = "memory_versions"
    __table_args__ = (
        UniqueConstraint("memory_id", "number", name="uq_memory_version_number"),
        CheckConstraint("number > 0", name="ck_version_number"),
        CheckConstraint("status IN ('ACTIVE', 'SUPERSEDED')", name="ck_version_status"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_version_time_range"),
        CheckConstraint("source_kind IN ('user', 'tool')", name="ck_version_source_kind"),
        Index("ix_version_memory", "memory_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    memory_id: Mapped[UUID] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_kind: Mapped[str] = mapped_column(String(16))
    source_agent: Mapped[str] = mapped_column(String(128))
    source_session: Mapped[str] = mapped_column(String(128))
    source_interaction: Mapped[str] = mapped_column(String(128))
    evidence: Mapped[str] = mapped_column(Text)


class MemoryEdge(Base):
    __tablename__ = "memory_edges"
    __table_args__ = (
        UniqueConstraint("from_version_id", "to_version_id", "relation", name="uq_memory_edge"),
        CheckConstraint("from_version_id <> to_version_id", name="ck_edge_no_self_link"),
        CheckConstraint(
            "relation IN ('supersedes', 'contradicts', 'related_to', 'derived_from')",
            name="ck_edge_relation",
        ),
        Index("ix_edge_target", "to_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    from_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE")
    )
    to_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE")
    )
    relation: Mapped[str] = mapped_column(String(16))
