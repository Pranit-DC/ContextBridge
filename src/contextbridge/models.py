from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, REAL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProviderQuota(Base):
    """Account-wide numeric usage only; no credentials, requests, or memory content."""

    __tablename__ = "provider_quotas"
    account_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[list] = mapped_column(JSON)
    day_started: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    day_tokens: Mapped[int] = mapped_column(Integer)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    claim_key: Mapped[str | None] = mapped_column(String(128))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryVersion(Base):
    __tablename__ = "memory_versions"
    __table_args__ = (
        UniqueConstraint("memory_id", "number", name="uq_memory_version_number"),
        CheckConstraint("number > 0", name="ck_version_number"),
        CheckConstraint("status IN ('ACTIVE', 'SUPERSEDED')", name="ck_version_status"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_version_time_range"),
        CheckConstraint("source_kind IN ('user', 'tool')", name="ck_version_source_kind"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_version_confidence",
        ),
        CheckConstraint(
            "decision_state IN ('clear', 'contested')", name="ck_version_decision_state"
        ),
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
    confidence: Mapped[float | None] = mapped_column()
    decision_state: Mapped[str] = mapped_column(String(16), server_default="clear")


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


class CaptureEvent(Base):
    __tablename__ = "capture_events"
    __table_args__ = (
        UniqueConstraint("developer_id", "event_id", name="uq_capture_owner_event"),
        CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_capture_scope",
        ),
        CheckConstraint("expires_at > received_at", name="ck_capture_retention"),
        CheckConstraint(
            "(payload IS NULL AND fingerprint IS NULL) OR "
            "(payload IS NOT NULL AND fingerprint IS NOT NULL)",
            name="ck_capture_payload_fingerprint",
        ),
        Index("ix_capture_owner_scope_expiry", "developer_id", "scope", "project_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(128))
    event_id: Mapped[UUID] = mapped_column()
    scope: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extraction_complete: Mapped[bool] = mapped_column(Boolean, server_default="false")


class CaptureJob(Base):
    __tablename__ = "capture_jobs"
    __table_args__ = (
        UniqueConstraint("event_record_id", name="uq_capture_job_event"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'deferred', 'failed', 'cancelled')",
            name="ck_capture_job_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("capture_events.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(16))
    reason_codes: Mapped[list] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retryable: Mapped[bool] = mapped_column(Boolean, server_default="false")
    group_leader_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("capture_jobs.id", ondelete="SET NULL"), index=True
    )


class CaptureCandidate(Base):
    __tablename__ = "capture_candidates"
    __table_args__ = (
        UniqueConstraint("developer_id", "candidate_id", name="uq_candidate_owner_id"),
        UniqueConstraint("job_id", "position", name="uq_candidate_job_position"),
        CheckConstraint("position >= 0", name="ck_candidate_position"),
        CheckConstraint(
            "status IN ('pending', 'rejected', 'deferred', 'applied', 'cancelled')",
            name="ck_candidate_status",
        ),
        CheckConstraint(
            "(payload IS NULL AND fingerprint IS NULL) OR "
            "(payload IS NOT NULL AND fingerprint IS NOT NULL)",
            name="ck_candidate_payload_fingerprint",
        ),
        Index("ix_candidate_job", "job_id"),
        Index("ix_candidate_expiry", "developer_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(128))
    candidate_id: Mapped[UUID] = mapped_column()
    position: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("capture_jobs.id", ondelete="CASCADE"))
    payload: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    reason_codes: Mapped[list] = mapped_column(JSON)
    admission: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    plan: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    comparison_version_ids: Mapped[list] = mapped_column(JSON)
    target_memory_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("memories.id", ondelete="SET NULL")
    )
    result_memory_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("memories.id", ondelete="SET NULL")
    )
    result_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL")
    )


class EmbeddingModel(Base):
    __tablename__ = "embedding_models"
    __table_args__ = (
        UniqueConstraint("developer_id", "model_id", "dimensions", name="uq_embedding_model_shape"),
        CheckConstraint("dimensions BETWEEN 1 AND 4096", name="ck_embedding_model_dimensions"),
    )

    developer_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dimensions: Mapped[int] = mapped_column(Integer)


class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["developer_id", "model_id", "dimensions"],
            [
                "embedding_models.developer_id",
                "embedding_models.model_id",
                "embedding_models.dimensions",
            ],
        ),
        CheckConstraint("cardinality(vector) = dimensions", name="ck_embedding_vector_dimensions"),
        CheckConstraint("array_ndims(vector) = 1", name="ck_embedding_vector_array"),
        CheckConstraint("array_position(vector, NULL) IS NULL", name="ck_embedding_vector_nonnull"),
        CheckConstraint(
            "NOT ('NaN'::real = ANY(vector) OR 'Infinity'::real = ANY(vector) "
            "OR '-Infinity'::real = ANY(vector))",
            name="ck_embedding_vector_finite",
        ),
        CheckConstraint(
            "vector <> array_fill(0::real, ARRAY[dimensions])", name="ck_embedding_vector_nonzero"
        ),
        Index("ix_embedding_owner_model", "developer_id", "model_id", "dimensions"),
    )

    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"), primary_key=True
    )
    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(128))
    dimensions: Mapped[int] = mapped_column(Integer)
    # Portable float32 storage also permits native core-only PostgreSQL deployments.
    # The semantic channel casts these arrays to pgvector for exact distance queries.
    vector: Mapped[list[float]] = mapped_column(ARRAY(REAL))
    content_fingerprint: Mapped[str] = mapped_column(String(64))
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReindexJob(Base):
    __tablename__ = "reindex_jobs"
    __table_args__ = (
        UniqueConstraint("developer_id", "request_id", name="uq_reindex_owner_request"),
        CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_reindex_scope",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'deferred', 'failed', 'cancelled')",
            name="ck_reindex_status",
        ),
        ForeignKeyConstraint(
            ["developer_id", "model_id", "dimensions"],
            [
                "embedding_models.developer_id",
                "embedding_models.model_id",
                "embedding_models.dimensions",
            ],
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[UUID] = mapped_column()
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[str | None] = mapped_column(String(128))
    model_id: Mapped[str] = mapped_column(String(128))
    dimensions: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    reason_codes: Mapped[list] = mapped_column(JSON)
    retryable: Mapped[bool] = mapped_column(Boolean, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReindexTarget(Base):
    __tablename__ = "reindex_targets"
    __table_args__ = (
        UniqueConstraint("job_id", "position", name="uq_reindex_target_position"),
        CheckConstraint("position >= 0 AND position < 200", name="ck_reindex_target_position"),
        Index("ix_reindex_target_version", "version_id"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("reindex_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)
    source_fingerprint: Mapped[str] = mapped_column(String(64))


class WorkItem(Base):
    """ID-only durable outbox, execution lease, and bounded diagnostics."""

    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint("kind", "job_id", name="uq_work_job"),
        CheckConstraint("kind IN ('capture', 'reindex', 'consolidation')", name="ck_work_kind"),
        CheckConstraint("attempts >= 0", name="ck_work_attempts"),
        CheckConstraint(
            "status IN ('queued', 'running', 'deferred', 'succeeded', 'failed', 'cancelled')",
            name="ck_work_status",
        ),
        CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_work_scope",
        ),
        Index("ix_work_delivery", "status", "available_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    job_id: Mapped[UUID] = mapped_column()
    developer_id: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsolidationJob(Base):
    __tablename__ = "consolidation_jobs"
    __table_args__ = (
        UniqueConstraint("developer_id", "request_id", name="uq_consolidation_request"),
        CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_consolidation_scope",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'deferred', 'failed', 'cancelled')",
            name="ck_consolidation_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(128))
    request_id: Mapped[UUID] = mapped_column()
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(16))
    project_id: Mapped[str | None] = mapped_column(String(128))
    conditions: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))
    reason_codes: Mapped[list] = mapped_column(JSON)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    proposals: Mapped[list | None] = mapped_column(JSON)
    result_memory_ids: Mapped[list] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsolidationSource(Base):
    __tablename__ = "consolidation_sources"
    __table_args__ = (
        UniqueConstraint("job_id", "position", name="uq_consolidation_position"),
        CheckConstraint("position >= 0 AND position < 200", name="ck_consolidation_position"),
        Index("ix_consolidation_source_version", "version_id"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("consolidation_jobs.id", ondelete="CASCADE"), primary_key=True
    )
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)
    source_fingerprint: Mapped[str] = mapped_column(String(64))


class CaptureBundle(Base):
    """ID/time/zone mapping only; source text remains in the bounded capture payload."""

    __tablename__ = "capture_bundles"
    event_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("capture_events.id", ondelete="CASCADE"), primary_key=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON)


class CandidateProvenance(Base):
    """Pending quote offsets and time bounds, erased with the candidate's raw artifacts."""

    __tablename__ = "candidate_provenance"
    candidate_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("capture_candidates.id", ondelete="CASCADE"), primary_key=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON)


class VersionProvenance(Base):
    """Visible durable source fragments and precision; forget cascades with the version."""

    __tablename__ = "version_provenance"
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="CASCADE"), primary_key=True
    )
    previous_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("memory_versions.id", ondelete="SET NULL"), index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON)
