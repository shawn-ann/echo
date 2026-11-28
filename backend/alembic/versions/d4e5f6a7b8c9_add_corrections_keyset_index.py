"""add corrections keyset index

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-28
"""

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_corrections_user_created_id",
        "corrections",
        ["user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_corrections_user_created_id", table_name="corrections")
