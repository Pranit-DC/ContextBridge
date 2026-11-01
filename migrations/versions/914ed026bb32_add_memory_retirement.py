"""Retirement closes effective validity while preserving content and evidence history.

Revision ID: 914ed026bb32
Revises: 803cd015aa21
"""

import sqlalchemy as sa
from alembic import op

revision = "914ed026bb32"
down_revision = "803cd015aa21"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memories", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("memories", "retired_at")
