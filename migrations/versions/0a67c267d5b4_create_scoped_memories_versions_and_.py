"""Create scoped memories versions and relationships

Revision ID: 0a67c267d5b4
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0a67c267d5b4"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("developer_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(scope = 'project' AND project_id IS NOT NULL) OR "
            "(scope = 'developer' AND project_id IS NULL)",
            name="ck_memory_scope",
        ),
        sa.CheckConstraint(
            "type IN ('FACT', 'DECISION', 'PREFERENCE', 'STATE', 'EVENT', 'LESSON')",
            name="ck_memory_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("developer_id", "request_id", name="uq_memory_write_request"),
    )
    op.create_index(
        "ix_memory_owner_scope", "memories", ["developer_id", "scope", "project_id"], unique=False
    )
    op.create_table(
        "memory_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("memory_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_agent", sa.String(length=128), nullable=False),
        sa.Column("source_session", sa.String(length=128), nullable=False),
        sa.Column("source_interaction", sa.String(length=128), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.CheckConstraint("source_kind IN ('user', 'tool')", name="ck_version_source_kind"),
        sa.CheckConstraint("status IN ('ACTIVE', 'SUPERSEDED')", name="ck_version_status"),
        sa.CheckConstraint("number > 0", name="ck_version_number"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_version_time_range"
        ),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "number", name="uq_memory_version_number"),
    )
    op.create_index("ix_version_memory", "memory_versions", ["memory_id"], unique=False)
    op.create_table(
        "memory_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_version_id", sa.Uuid(), nullable=False),
        sa.Column("to_version_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "relation IN ('supersedes', 'contradicts', 'related_to', 'derived_from')",
            name="ck_edge_relation",
        ),
        sa.CheckConstraint("from_version_id <> to_version_id", name="ck_edge_no_self_link"),
        sa.ForeignKeyConstraint(["from_version_id"], ["memory_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_version_id"], ["memory_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_version_id", "to_version_id", "relation", name="uq_memory_edge"),
    )
    op.create_index("ix_edge_target", "memory_edges", ["to_version_id"], unique=False)


def downgrade():
    op.drop_index("ix_edge_target", table_name="memory_edges")
    op.drop_table("memory_edges")
    op.drop_index("ix_version_memory", table_name="memory_versions")
    op.drop_table("memory_versions")
    op.drop_index("ix_memory_owner_scope", table_name="memories")
    op.drop_table("memories")
