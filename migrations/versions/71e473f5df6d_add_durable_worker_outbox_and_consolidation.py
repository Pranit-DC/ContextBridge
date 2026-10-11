"""add durable worker outbox and consolidation jobs

Revision ID: 71e473f5df6d
Revises: 70693e8576e5
"""

import sqlalchemy as sa
from alembic import op

revision = "71e473f5df6d"
down_revision = "70693e8576e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "consolidation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("developer_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("proposals", sa.JSON(), nullable=True),
        sa.Column("result_memory_ids", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_consolidation_scope",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'deferred', 'failed', 'cancelled')",
            name="ck_consolidation_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("developer_id", "request_id", name="uq_consolidation_request"),
    )
    op.create_table(
        "work_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("developer_id", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_work_scope",
        ),
        sa.CheckConstraint("kind IN ('capture', 'reindex', 'consolidation')", name="ck_work_kind"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'deferred', 'succeeded', 'failed', 'cancelled')",
            name="ck_work_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_work_attempts"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "job_id", name="uq_work_job"),
    )
    op.create_index("ix_work_delivery", "work_items", ["status", "available_at"], unique=False)
    op.create_table(
        "consolidation_sources",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint("position >= 0 AND position < 200", name="ck_consolidation_position"),
        sa.ForeignKeyConstraint(["job_id"], ["consolidation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["memory_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "version_id"),
        sa.UniqueConstraint("job_id", "position", name="uq_consolidation_position"),
    )
    op.create_index(
        "ix_consolidation_source_version", "consolidation_sources", ["version_id"], unique=False
    )


def downgrade():
    op.drop_index("ix_consolidation_source_version", table_name="consolidation_sources")
    op.drop_table("consolidation_sources")
    op.drop_index("ix_work_delivery", table_name="work_items")
    op.drop_table("work_items")
    op.drop_table("consolidation_jobs")
