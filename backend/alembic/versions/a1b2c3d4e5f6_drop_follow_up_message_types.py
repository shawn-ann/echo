"""drop follow_up and reply message types (single-round correction)

Revision ID: a1b2c3d4e5f6
Revises: 85fe55bcdebc
Create Date: 2026-08-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '85fe55bcdebc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 follow_up/reply 消息类型，实现单轮纠错。

    先清理历史消息，再通过「新建枚举类型 + 列类型迁移 + 替换」移除枚举值
    （PG 不支持 ALTER TYPE ... DROP VALUE）。
    """
    op.execute("DELETE FROM messages WHERE type IN ('follow_up', 'reply')")
    op.execute("ALTER TYPE message_type RENAME TO message_type_old")
    op.execute("CREATE TYPE message_type AS ENUM ('correction', 'report')")
    op.execute(
        "ALTER TABLE messages ALTER COLUMN type TYPE message_type "
        "USING type::text::message_type"
    )
    op.execute("DROP TYPE message_type_old")


def downgrade() -> None:
    """恢复 follow_up/reply 枚举值（同样用类型重建方式）。"""
    op.execute("ALTER TYPE message_type RENAME TO message_type_new")
    op.execute(
        "CREATE TYPE message_type AS ENUM ('correction', 'report', 'follow_up', 'reply')"
    )
    op.execute(
        "ALTER TABLE messages ALTER COLUMN type TYPE message_type "
        "USING type::text::message_type"
    )
    op.execute("DROP TYPE message_type_new")
