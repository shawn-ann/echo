"""add note examples and refactor note_cases

Revision ID: f1fd79983847
Revises: c8dc822826e5
Create Date: 2026-08-30 11:33:43.837551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1fd79983847'
down_revision: Union[str, Sequence[str], None] = 'c8dc822826e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # notes 新增 examples
    op.add_column('notes', sa.Column('examples', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    # note_cases 清空（存量 example 清空重建，用户已确认）
    op.execute("TRUNCATE TABLE note_cases")
    # example 改名 fragment
    op.alter_column('note_cases', 'example', new_column_name='fragment')
    # 新增 correction 列
    op.add_column('note_cases', sa.Column('correction', sa.Text(), nullable=False, server_default=''))
    op.alter_column('note_cases', 'correction', server_default=None)
    # 新增唯一约束
    op.create_unique_constraint('uq_note_cases_dedup', 'note_cases', ['note_id', 'user_id', 'source_text', 'fragment'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_note_cases_dedup', 'note_cases', type_='unique')
    op.drop_column('note_cases', 'correction')
    op.alter_column('note_cases', 'fragment', new_column_name='example')
    op.drop_column('notes', 'examples')
