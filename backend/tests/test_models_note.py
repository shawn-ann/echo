import uuid

from sqlalchemy import select

from app.db import async_session_factory
from app.models.note import Note, NoteCase
from app.models.user import User


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_create_note_with_examples():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(
            rule_title="第三人称单数主谓一致",
            description="一般现在时中，第三人称单数主语动词加 -s/-es",
            examples=[
                {"text": "She plays tennis.", "note": "play → plays"},
                {"text": "He goes to work.", "note": "go → goes"},
            ],
        )
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            fragment="She have",
            correction="She has",
            source_text="She have many book",
        )
        s.add(case)
        await s.commit()
        assert note.id is not None
        assert note.examples == [
            {"text": "She plays tennis.", "note": "play → plays"},
            {"text": "He goes to work.", "note": "go → goes"},
        ]
        assert case.fragment == "She have"
        assert case.correction == "She has"


async def test_note_examples_default_empty():
    async with async_session_factory() as s:
        note = Note(rule_title="测试规则", description="测试")
        s.add(note)
        await s.commit()
        assert note.examples == []


async def test_note_case_unique_dedup():
    """同 (note, user, source_text, fragment) 唯一：重复插入抛 IntegrityError"""
    from sqlalchemy.exc import IntegrityError

    import pytest

    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="唯一约束规则", description="测试")
        s.add(note)
        await s.flush()
        s.add(NoteCase(note_id=note.id, user_id=uid, fragment="She have", correction="She has", source_text="src"))
        await s.commit()
    async with async_session_factory() as s:
        with pytest.raises(IntegrityError):
            s.add(NoteCase(note_id=note.id, user_id=uid, fragment="She have", correction="She has", source_text="src"))
            await s.commit()


async def test_note_case_cascade_delete_note():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(rule_title="级联规则", description="测试")
        s.add(note)
        await s.flush()
        case_id = uuid.uuid4()
        s.add(NoteCase(id=case_id, note_id=note.id, user_id=uid, fragment="f", correction="c", source_text="src"))
        await s.commit()
        await s.delete(note)
        await s.commit()
    async with async_session_factory() as s:
        assert (await s.get(NoteCase, case_id)) is None


async def test_delete_message_keeps_case():
    from app.models.conversation import SessionConversation
    from app.models.message import Message, MessageRole, MessageType

    uid = await _demo_user_id()
    async with async_session_factory() as s:
        conv = SessionConversation(user_id=uid)
        s.add(conv)
        await s.flush()
        msg = Message(conversation_id=conv.id, role=MessageRole.user, type=MessageType.correction, content="test")
        s.add(msg)
        await s.flush()
        note = Note(rule_title="消息规则", description="测试")
        s.add(note)
        await s.flush()
        case = NoteCase(note_id=note.id, user_id=uid, fragment="f", correction="c", source_text="src", source_message_id=msg.id)
        s.add(case)
        await s.commit()
        case_id = case.id
        await s.delete(msg)
        await s.commit()
    async with async_session_factory() as s:
        refreshed = await s.get(NoteCase, case_id)
        assert refreshed is not None
        assert refreshed.source_message_id is None
