import json
import uuid

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.db import async_session_factory
from app.models.note import Note, NoteCase
from app.models.user import User
from app.services.llm_client import LLMTimeoutError, LLMUnavailableError, MockLLMClient
from app.services.note_service import save_notes


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


def _mock_responder_new_rule(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "介词后加 -ing 形式",
            "description": "介词后接动词用动名词形式",
            "example": "interested in read → interested in reading",
        }]
    }, ensure_ascii=False)


async def test_save_new_rule_creates_note_and_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        result = await save_notes(
            s, uid, None, "I interested in read",
            [{"error_type": "动词形式", "fragment": "interested in read",
              "explanation": "介词后加 ing", "correction": "interested in reading"}],
            mock,
        )
        assert len(result) == 1
        assert result[0].is_new is True
        assert result[0].rule_title == "介词后加 -ing 形式"


def _mock_responder_existing_rule(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "介词后加 -ing 形式",
            "description": "（后端忽略，已有规则）",
            "example": "good at swim → good at swimming",
        }]
    }, ensure_ascii=False)


async def test_save_existing_rule_appends_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(
            s, uid, None, "I interested in read",
            [{"error_type": "动词形式", "fragment": "interested in read",
              "explanation": "x", "correction": "interested in reading"}],
            mock,
        )

    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder_existing_rule)
        result = await save_notes(
            s, uid, None, "She is good at swim",
            [{"error_type": "动词形式", "fragment": "good at swim",
              "explanation": "x", "correction": "good at swimming"}],
            mock2,
        )
        assert len(result) == 1
        assert result[0].is_new is False

    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "介词后加 -ing 形式"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2


def _mock_responder_two_rules(msgs):
    return json.dumps({
        "results": [
            {"rule_title": "介词后加 -ing 形式", "description": "d1", "example": "e1 → e2"},
            {"rule_title": "to 不定式接原形", "description": "d2", "example": "e3 → e4"},
        ]
    }, ensure_ascii=False)


async def test_save_batch_creates_multiple_rules():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_two_rules)
        result = await save_notes(
            s, uid, None, "source text",
            [
                {"error_type": "动词形式", "fragment": "f1", "explanation": "x", "correction": "c1"},
                {"error_type": "动词形式", "fragment": "f2", "explanation": "x", "correction": "c2"},
            ],
            mock,
        )
        assert len(result) == 2
        assert all(r.is_new for r in result)


class _RaisingLLMClient:
    def __init__(self, exc):
        self._exc = exc

    async def complete(self, messages):
        raise self._exc


async def test_save_timeout_raises_504():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMTimeoutError())
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 504


async def test_save_llm_unavailable_raises_503():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMUnavailableError())
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 503


def _mock_responder_invalid(msgs):
    return "not-json"


async def test_save_invalid_llm_response_raises_502():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_invalid)
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 502


from app.services.note_service import list_notes, get_note_detail, delete_note, delete_case


async def test_list_notes_returns_user_notes_with_count():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_two_rules)
        await save_notes(s, uid, None, "src", [
            {"error_type": "t", "fragment": "f1", "explanation": "e", "correction": "c"},
            {"error_type": "t", "fragment": "f2", "explanation": "e", "correction": "c"},
        ], mock)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        assert len(notes) == 2
        assert all(n.case_count == 1 for n in notes)


async def test_list_notes_isolates_by_user():
    from app.core.security import hash_password
    from app.models.user import UserStatus

    async with async_session_factory() as s:
        s.add(User(username="alice2", password_hash=hash_password("a1234"), status=UserStatus.active))
        await s.commit()
        alice = (await s.execute(select(User).where(User.username == "alice2"))).scalar_one()
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "src", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
    async with async_session_factory() as s:
        alice_notes = await list_notes(s, alice.id)
        assert alice_notes == []


async def test_get_note_detail_includes_cases():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "I interested in read", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        detail = await get_note_detail(s, uid, notes[0].id)
        assert detail.rule_title == "介词后加 -ing 形式"
        assert len(detail.cases) == 1
        assert detail.cases[0].source_text == "I interested in read"


async def test_get_note_detail_other_user_returns_none():
    from app.core.security import hash_password
    from app.models.user import UserStatus

    async with async_session_factory() as s:
        s.add(User(username="bob2", password_hash=hash_password("b1234"), status=UserStatus.active))
        await s.commit()
        bob = (await s.execute(select(User).where(User.username == "bob2"))).scalar_one()
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "src", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        notes = await list_notes(s, uid)
        note_id = notes[0].id
    async with async_session_factory() as s:
        detail = await get_note_detail(s, bob.id, note_id)
        assert detail is None


async def test_delete_note_removes_user_cases_keeps_global():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "src", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        notes = await list_notes(s, uid)
        note_id = notes[0].id
    async with async_session_factory() as s:
        await delete_note(s, uid, note_id)
    async with async_session_factory() as s:
        assert await s.get(Note, note_id) is not None  # 全局规则保留
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note_id))).scalars().all()
        assert all(c.user_id != uid for c in cases)


async def test_delete_case_removes_single_case():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "first", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder_existing_rule)
        await save_notes(s, uid, None, "second", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock2)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        detail = await get_note_detail(s, uid, notes[0].id)
        case_id = detail.cases[0].id
        await delete_case(s, uid, case_id)
    async with async_session_factory() as s:
        notes = await list_notes(s, uid)
        assert notes[0].case_count == 1
