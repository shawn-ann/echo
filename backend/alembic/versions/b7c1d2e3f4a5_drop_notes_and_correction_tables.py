"""drop notes and legacy correction tables

Revision ID: b7c1d2e3f4a5
Revises: d2ac8e32a24c
Create Date: 2026-11-26
"""

from alembic import op

revision = "b7c1d2e3f4a5"
down_revision = "d2ac8e32a24c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS note_cases CASCADE")
    op.execute("DROP TABLE IF EXISTS notes CASCADE")
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TABLE IF EXISTS correction_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS session_conversations CASCADE")
    op.execute("DROP TYPE IF EXISTS message_role")
    op.execute("DROP TYPE IF EXISTS message_type")


def downgrade() -> None:
    # 数据已删除，无法恢复；需要恢复请从备份重建。
    raise RuntimeError("drop_notes_and_correction_tables is irreversible")
