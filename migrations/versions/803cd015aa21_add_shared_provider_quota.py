"""Shared numeric provider limits, without stored credentials or source content.

Revision ID: 803cd015aa21
Revises: 71e473f5df6d
"""

import sqlalchemy as sa
from alembic import op

revision = "803cd015aa21"
down_revision = "71e473f5df6d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provider_quotas",
        sa.Column("account_hash", sa.String(64), primary_key=True),
        sa.Column("window", sa.JSON(), nullable=False),
        sa.Column("day_started", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day_tokens", sa.Integer(), nullable=False),
        sa.Column("next_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("provider_quotas")
