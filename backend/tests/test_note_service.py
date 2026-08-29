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
