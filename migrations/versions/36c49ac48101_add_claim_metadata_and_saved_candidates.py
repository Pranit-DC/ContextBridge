"""Add claim metadata and durable candidate interpretation (P2).

Revision ID: 36c49ac48101
Revises: 24b179ad6c31
"""

import sqlalchemy as sa
from alembic import op

revision = "36c49ac48101"
down_revision = "24b179ad6c31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memories", sa.Column("claim_key", sa.String(128), nullable=True))
    op.add_column("memory_versions", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column(
        "memory_versions",
        sa.Column("decision_state", sa.String(16), nullable=False, server_default="clear"),
    )
    op.create_check_constraint(
        "ck_version_confidence",
        "memory_versions",
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
    )
    op.create_check_constraint(
        "ck_version_decision_state", "memory_versions", "decision_state IN ('clear', 'contested')"
    )
    op.add_column(
        "capture_events",
        sa.Column("extraction_complete", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "capture_jobs", sa.Column("retryable", sa.Boolean(), nullable=False, server_default="false")
    )
    op.create_table(
        "capture_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("developer_id", sa.String(128), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("admission", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("plan", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("comparison_version_ids", sa.JSON(), nullable=False),
        sa.Column("target_memory_id", sa.Uuid(), nullable=True),
        sa.Column("result_memory_id", sa.Uuid(), nullable=True),
        sa.Column("result_version_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("developer_id", "candidate_id", name="uq_candidate_owner_id"),
        sa.UniqueConstraint("job_id", "position", name="uq_candidate_job_position"),
        sa.CheckConstraint("position >= 0", name="ck_candidate_position"),
        sa.ForeignKeyConstraint(["job_id"], ["capture_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_memory_id"], ["memories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["result_memory_id"], ["memories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["result_version_id"], ["memory_versions.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('pending', 'rejected', 'deferred', 'applied', 'cancelled')",
            name="ck_candidate_status",
        ),
        sa.CheckConstraint(
            "(payload IS NULL AND fingerprint IS NULL) OR "
            "(payload IS NOT NULL AND fingerprint IS NOT NULL)",
            name="ck_candidate_payload_fingerprint",
        ),
    )
    op.create_index("ix_candidate_job", "capture_candidates", ["job_id"])
    op.create_index("ix_candidate_expiry", "capture_candidates", ["developer_id", "expires_at"])


def downgrade():
    op.drop_index("ix_candidate_expiry", table_name="capture_candidates")
    op.drop_index("ix_candidate_job", table_name="capture_candidates")
    op.drop_table("capture_candidates")
    op.drop_column("capture_jobs", "retryable")
    op.drop_column("capture_events", "extraction_complete")
    op.drop_constraint("ck_version_decision_state", "memory_versions", type_="check")
    op.drop_constraint("ck_version_confidence", "memory_versions", type_="check")
    op.drop_column("memory_versions", "decision_state")
    op.drop_column("memory_versions", "confidence")
    op.drop_column("memories", "claim_key")
