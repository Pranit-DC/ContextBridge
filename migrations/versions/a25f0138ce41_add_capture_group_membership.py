"""ID-only frozen capture group membership; existing jobs remain independent.

Revision ID: a25f0138ce41
Revises: 914ed026bb32
"""

import sqlalchemy as sa
from alembic import op

revision = "a25f0138ce41"
down_revision = "914ed026bb32"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("capture_jobs", sa.Column("group_leader_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_capture_group_leader",
        "capture_jobs",
        "capture_jobs",
        ["group_leader_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_capture_jobs_group_leader_id", "capture_jobs", ["group_leader_id"])


def downgrade():
    op.drop_index("ix_capture_jobs_group_leader_id", table_name="capture_jobs")
    op.drop_constraint("fk_capture_group_leader", "capture_jobs", type_="foreignkey")
    op.drop_column("capture_jobs", "group_leader_id")
