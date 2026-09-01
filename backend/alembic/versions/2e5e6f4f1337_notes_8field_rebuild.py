"""notes 8field rebuild

Revision ID: 2e5e6f4f1337
Revises: f1fd79983847
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2e5e6f4f1337'
down_revision: Union[str, Sequence[str], None] = 'f1fd79983847'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('note_cases')
    op.drop_table('notes')

    op.create_table('notes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('rule_title', sa.String(length=200), nullable=False),
    sa.Column('knowledge_point', sa.Text(), nullable=False),
    sa.Column('warning', sa.Text(), nullable=False),
    sa.Column('alternatives', postgresql.JSONB(), nullable=False),
    sa.Column('feynman_question', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_notes_user_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'rule_title', name='uq_notes_user_rule_title')
    )
    op.create_table('note_cases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('note_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('original_sentence', sa.Text(), nullable=False),
    sa.Column('polished_sentence', sa.Text(), nullable=False),
    sa.Column('change_details', sa.Text(), nullable=False),
    sa.Column('error_root', sa.Text(), nullable=False),
    sa.Column('source_message_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['notes.id'], name='fk_note_cases_note_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], name='fk_note_cases_message_id', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_note_cases_user_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('note_id', 'user_id', 'original_sentence', name='uq_note_cases_dedup')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('note_cases')
    op.drop_table('notes')
    op.create_table('notes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('rule_title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('examples', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('note_cases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('note_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('fragment', sa.Text(), nullable=False),
    sa.Column('correction', sa.Text(), nullable=False),
    sa.Column('source_text', sa.Text(), nullable=False),
    sa.Column('source_message_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['notes.id'], name='fk_note_cases_note_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_message_id'], ['messages.id'], name='fk_note_cases_message_id', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_note_cases_user_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('note_id', 'user_id', 'source_text', 'fragment', name='uq_note_cases_dedup')
    )
