import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import async_session_factory
from app.models.note import Note, NoteCase
from app.models.user import User


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def test_create_note_fields():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(
            user_id=uid,
            rule_title="第三人称单数主谓一致",
            knowledge_point="一般现在时中，第三人称单数主语动词加 -s/-es",
            alternatives=["She runs.", "He goes."],
            feynman_question="主语是 she/he/it 时动词怎么变？",
        )
        s.add(note)
        await s.flush()
        case = NoteCase(
            note_id=note.id,
            user_id=uid,
            original_sentence="She go to school.",
            polished_sentence="She goes to school.",
            change_details="She go → She goes",
            error_root="主谓不一致",
        )
        s.add(case)
        await s.commit()
        assert note.id is not None
        assert note.user_id == uid
        assert note.alternatives == ["She runs.", "He goes."]
        assert case.original_sentence == "She go to school."
        assert case.polished_sentence == "She goes to school."
        assert case.change_details == "She go → She goes"
        assert case.error_root == "主谓不一致"


async def test_notes_allow_same_title_different_users():
    """同 rule_title 不同 user 可共存（无 (user_id, rule_title) 唯一约束）"""
    uid1 = await _demo_user_id()
    async with async_session_factory() as s:
        from app.core.security import hash_password
        from app.models.user import User, UserStatus
        s.add(User(username="notes_other_u", password_hash=hash_password("other1234"), status=UserStatus.active))
        await s.commit()
        uid2 = (await s.execute(select(User).where(User.username == "notes_other_u"))).scalar_one().id
        s.add(Note(user_id=uid1, rule_title="同标题规则", knowledge_point="kp", feynman_question="q"))
        s.add(Note(user_id=uid2, rule_title="同标题规则", knowledge_point="kp", feynman_question="q"))
        await s.commit()


async def test_note_cases_unique_note_user_original():
    """同 (note_id, user_id, original_sentence) 唯一：重复插入抛 IntegrityError"""
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(user_id=uid, rule_title="唯一约束规则", knowledge_point="kp", feynman_question="q")
        s.add(note)
        await s.flush()
        s.add(NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
        await s.commit()
    async with async_session_factory() as s:
        with pytest.raises(IntegrityError):
            s.add(NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
            await s.commit()


async def test_note_case_cascade_delete_note():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        note = Note(user_id=uid, rule_title="级联规则", knowledge_point="kp", feynman_question="q")
        s.add(note)
        await s.flush()
        case_id = uuid.uuid4()
        s.add(NoteCase(id=case_id, note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r"))
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
        note = Note(user_id=uid, rule_title="消息规则", knowledge_point="kp", feynman_question="q")
        s.add(note)
        await s.flush()
        case = NoteCase(note_id=note.id, user_id=uid, original_sentence="src", polished_sentence="fix", change_details="d", error_root="r", source_message_id=msg.id)
        s.add(case)
        await s.commit()
        case_id = case.id
        await s.delete(msg)
        await s.commit()
    async with async_session_factory() as s:
        refreshed = await s.get(NoteCase, case_id)
        assert refreshed is not None
        assert refreshed.source_message_id is None
