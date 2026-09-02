"""drop notes user rule_title unique constraint

Revision ID: 093ea062b62f
Revises: 2e5e6f4f1337
Create Date: 2026-09-02 08:20:35.920555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '093ea062b62f'
down_revision: Union[str, Sequence[str], None] = '2e5e6f4f1337'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('uq_notes_user_rule_title', 'notes', type_='unique')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_unique_constraint('uq_notes_user_rule_title', 'notes', ['user_id', 'rule_title'])
