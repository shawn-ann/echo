import uuid

import pytest
from sqlalchemy import select

from app.db import async_session_factory, Base
from app.models.note import Note, NoteCase
from app.models.user import User


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_create_note_and_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="介词后加 -ing 形式", description="介词后接动词用动名词形式")
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            example="interested in read → interested in reading",
            source_text="I interested in read",
        )
        s.add(case)
        await s.commit()
        assert note.id is not None
        assert case.id is not None
        assert note.created_at is not None
        assert note.updated_at is not None


async def test_note_case_cascade_delete_note():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="to 不定式接原形", description="to 作不定式时后接动词原形")
        s.add(note)
        await s.flush()
        case_id = uuid.uuid4()
        s.add(NoteCase(
            id=case_id,
            note_id=note.id,
            user_id=uid,
            example="to began → to begin",
            source_text="I want to began",
        ))
        await s.commit()
        await s.delete(note)
        await s.commit()
    async with async_session_factory() as s:
        assert (await s.get(NoteCase, case_id)) is None


async def test_delete_message_keeps_case():
    """source_message_id 用 SET NULL：删消息不删案例"""
    from app.models.conversation import SessionConversation
    from app.models.message import Message, MessageRole, MessageType

    uid = await _demo_user_id()
    async with async_session_factory() as s:
        conv = SessionConversation(user_id=uid)
        s.add(conv)
        await s.flush()
        msg = Message(
            conversation_id=conv.id,
            role=MessageRole.user,
            type=MessageType.correction,
            content="test",
        )
        s.add(msg)
        await s.flush()
        note = Note(rule_title="测试规则", description="测试")
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            example="wrong → right",
            source_text="test",
            source_message_id=msg.id,
        )
        s.add(case)
        await s.commit()
        case_id = case.id
        await s.delete(msg)
        await s.commit()
    async with async_session_factory() as s:
        refreshed = await s.get(NoteCase, case_id)
        assert refreshed is not None
        assert refreshed.source_message_id is None
