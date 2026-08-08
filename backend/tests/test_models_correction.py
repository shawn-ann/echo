import pytest
from sqlalchemy import select

from app.db import async_session_factory
from app.models.conversation import SessionConversation
from app.models.message import Message, MessageRole, MessageType
from app.models.report import CorrectionReport
from app.models.user import User


async def test_models_importable_and_roundtrip():
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        conv = SessionConversation(user_id=user.id)
        s.add(conv)
        await s.flush()
        msg = Message(
            conversation_id=conv.id,
            role=MessageRole.user,
            type=MessageType.correction,
            content="hello",
        )
        s.add(msg)
        await s.flush()
        rep = CorrectionReport(message_id=msg.id, version=1, structure={"a": 1})
        s.add(rep)
        await s.flush()
        msg.report_id = rep.id
        await s.commit()

        rows = (await s.execute(select(Message))).scalars().all()
        assert len(rows) == 1
        assert rows[0].report_id == rep.id
