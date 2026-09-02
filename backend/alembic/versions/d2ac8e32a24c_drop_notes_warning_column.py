"""drop notes warning column

Revision ID: d2ac8e32a24c
Revises: 093ea062b62f
Create Date: 2026-09-02 21:51:40.229129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2ac8e32a24c'
down_revision: Union[str, Sequence[str], None] = '093ea062b62f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 使用 IF EXISTS：本地开发库可能已手动删除该列，保证幂等
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS warning")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('notes', sa.Column('warning', sa.Text(), nullable=False, server_default=''))
    op.alter_column('notes', 'warning', server_default=None)
