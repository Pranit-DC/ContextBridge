"""Add durable capture events and jobs without changing explicit memories.

Revision ID: 24b179ad6c31
Revises: 0a67c267d5b4
"""

import sqlalchemy as sa
from alembic import op

revision = "24b179ad6c31"
down_revision = "0a67c267d5b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "capture_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("developer_id", sa.String(128), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=True),
        sa.Column("payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("developer_id", "event_id", name="uq_capture_owner_event"),
        sa.CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_capture_scope",
        ),
        sa.CheckConstraint("expires_at > received_at", name="ck_capture_retention"),
        sa.CheckConstraint(
            "(payload IS NULL AND fingerprint IS NULL) OR "
            "(payload IS NOT NULL AND fingerprint IS NOT NULL)",
            name="ck_capture_payload_fingerprint",
        ),
    )
    op.create_index(
        "ix_capture_owner_scope_expiry",
        "capture_events",
        ["developer_id", "scope", "project_id", "expires_at"],
    )
    op.create_table(
        "capture_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_record_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_record_id"], ["capture_events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_record_id", name="uq_capture_job_event"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'deferred', 'failed', 'cancelled')",
            name="ck_capture_job_status",
        ),
    )


def downgrade():
    op.drop_table("capture_jobs")
    op.drop_index("ix_capture_owner_scope_expiry", table_name="capture_events")
    op.drop_table("capture_events")
