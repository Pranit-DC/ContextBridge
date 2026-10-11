"""Add version embeddings and durable reindex batches.

Revision ID: 70693e8576e5
Revises: 36c49ac48101
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "70693e8576e5"
down_revision = "36c49ac48101"
branch_labels = None
depends_on = None


def upgrade():
    # Keep the portable schema on core-only native PostgreSQL. Vector containers
    # activate the installed extension; retrieval reports a missing extension safely.
    available = op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector')")
    )
    if available:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "embedding_models",
        sa.Column("developer_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.CheckConstraint("dimensions BETWEEN 1 AND 4096", name="ck_embedding_model_dimensions"),
        sa.PrimaryKeyConstraint("developer_id", "model_id"),
        sa.UniqueConstraint(
            "developer_id", "model_id", "dimensions", name="uq_embedding_model_shape"
        ),
    )
    op.create_table(
        "reindex_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("developer_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=True),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("retryable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_reindex_scope",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'deferred', 'failed', 'cancelled')",
            name="ck_reindex_status",
        ),
        sa.ForeignKeyConstraint(
            ["developer_id", "model_id", "dimensions"],
            [
                "embedding_models.developer_id",
                "embedding_models.model_id",
                "embedding_models.dimensions",
            ],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("developer_id", "request_id", name="uq_reindex_owner_request"),
    )
    op.create_table(
        "memory_embeddings",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("developer_id", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", postgresql.ARRAY(sa.REAL()), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("array_ndims(vector) = 1", name="ck_embedding_vector_array"),
        sa.CheckConstraint(
            "array_position(vector, NULL) IS NULL", name="ck_embedding_vector_nonnull"
        ),
        sa.CheckConstraint(
            "NOT ('NaN'::real = ANY(vector) OR 'Infinity'::real = ANY(vector) "
            "OR '-Infinity'::real = ANY(vector))",
            name="ck_embedding_vector_finite",
        ),
        sa.CheckConstraint(
            "vector <> array_fill(0::real, ARRAY[dimensions])", name="ck_embedding_vector_nonzero"
        ),
        sa.CheckConstraint(
            "cardinality(vector) = dimensions", name="ck_embedding_vector_dimensions"
        ),
        sa.ForeignKeyConstraint(
            ["developer_id", "model_id", "dimensions"],
            [
                "embedding_models.developer_id",
                "embedding_models.model_id",
                "embedding_models.dimensions",
            ],
        ),
        sa.ForeignKeyConstraint(["version_id"], ["memory_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id", "model_id"),
    )
    op.create_index(
        "ix_embedding_owner_model",
        "memory_embeddings",
        ["developer_id", "model_id", "dimensions"],
        unique=False,
    )
    op.create_table(
        "reindex_targets",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint("position >= 0 AND position < 200", name="ck_reindex_target_position"),
        sa.ForeignKeyConstraint(["job_id"], ["reindex_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["memory_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "version_id"),
        sa.UniqueConstraint("job_id", "position", name="uq_reindex_target_position"),
    )
    op.create_index("ix_reindex_target_version", "reindex_targets", ["version_id"])


def downgrade():
    # Preserve a pre-existing/shared extension when removing application tables.
    op.drop_index("ix_reindex_target_version", table_name="reindex_targets")
    op.drop_table("reindex_targets")
    op.drop_index("ix_embedding_owner_model", table_name="memory_embeddings")
    op.drop_table("memory_embeddings")
    op.drop_table("reindex_jobs")
    op.drop_table("embedding_models")
