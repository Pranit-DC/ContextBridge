"""Opt-in multi-source provenance; existing memory/capture rows remain unchanged.

Revision ID: b31d405a9a62
Revises: a25f0138ce41
"""

import sqlalchemy as sa
from alembic import op

revision = "b31d405a9a62"
down_revision = "a25f0138ce41"
branch_labels = None
depends_on = None


def upgrade():
    for table, key, target in [
        ("capture_bundles", "event_record_id", "capture_events.id"),
        ("candidate_provenance", "candidate_record_id", "capture_candidates.id"),
        ("version_provenance", "version_id", "memory_versions.id"),
    ]:
        op.create_table(
            table,
            sa.Column(key, sa.Uuid(), sa.ForeignKey(target, ondelete="CASCADE"), primary_key=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
        )
    op.add_column("version_provenance", sa.Column("previous_version_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_provenance_previous",
        "version_provenance",
        "memory_versions",
        ["previous_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_version_provenance_previous_version_id", "version_provenance", ["previous_version_id"]
    )


def downgrade():
    for table in ["version_provenance", "candidate_provenance", "capture_bundles"]:
        op.drop_table(table)
