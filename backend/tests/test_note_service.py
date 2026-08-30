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
            "rule_title": "第三人称单数主谓一致",
            "description": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "examples": [
                {"text": "She plays tennis.", "note": "play → plays"},
                {"text": "He goes to work.", "note": "go → goes"},
                {"text": "It rains a lot.", "note": "rain → rains"},
            ],
            "references": ["She have", "she go"],
        }]
    }, ensure_ascii=False)


async def test_save_new_rule_creates_note_with_examples_and_cases():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "主谓不一致", "fragment": "she go", "explanation": "x", "correction": "she goes"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        result = await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
        assert len(result) == 2
        assert all(r.is_new for r in result)
        assert all(r.rule_title == "第三人称单数主谓一致" for r in result)

    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        assert len(note.examples) == 3
        assert note.examples[0]["text"] == "She plays tennis."
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2
        by_fragment = {c.fragment: c.correction for c in cases}
        assert by_fragment["She have"] == "She has"
        assert by_fragment["she go"] == "she goes"


def _mock_responder_existing_rule(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "description": "（后端忽略，已有规则）",
            "examples": [{"text": "ignored", "note": "ignored"}],
            "references": ["He have"],
        }]
    }, ensure_ascii=False)


async def test_save_existing_rule_ignores_examples_and_appends_case():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "主谓不一致", "fragment": "she go", "explanation": "x", "correction": "she goes"},
    ]
    # 先新建规则
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
    # 再用已有规则保存（新原文，references 不同）
    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder_existing_rule)
        result = await save_notes(s, uid, None, "He have a car", [{"error_type": "主谓不一致", "fragment": "He have", "explanation": "x", "correction": "He has"}], mock2)
        assert len(result) == 1
        assert result[0].is_new is False
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        assert len(note.examples) == 3  # 未被覆盖（忽略 LLM 的 examples）
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 3  # 2 (首建) + 1 (追加)


async def test_save_dedup_same_source_and_fragment():
    """同一原文+同一错误段重复保存：只保留一条（先查重 + 唯一约束兜底）"""
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "主谓不一致", "fragment": "she go", "explanation": "x", "correction": "she goes"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_new_rule)
        # 保存两次同一原文同一错误
        await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
        result = await save_notes(s, uid, None, "She have many book and she go to school", errors, mock)
        assert len(result) == 0  # 全部重复，跳过
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 2  # 仍只有 2 条


async def test_save_reference_without_matching_error_skipped():
    """LLM references 含不在 errors 中的 fragment：静默跳过"""
    uid = await _demo_user_id()
    errors = [{"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"}]
    responder = lambda msgs: json.dumps({
        "results": [{
            "rule_title": "测试规则",
            "description": "d",
            "examples": [],
            "references": ["She have", "not in errors"],
        }]
    }, ensure_ascii=False)
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=responder)
        result = await save_notes(s, uid, None, "She have many book", errors, mock)
        assert len(result) == 1  # 只有 She have 匹配到 correction
    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "测试规则"))).scalar_one()
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 1


def _mock_responder_two_rules(msgs):
    return json.dumps({
        "results": [
            {"rule_title": "主谓一致规则", "description": "d1", "examples": [], "references": ["She have"]},
            {"rule_title": "单复数规则", "description": "d2", "examples": [], "references": ["many book"]},
        ]
    }, ensure_ascii=False)


async def test_save_batch_creates_multiple_rules():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She have", "explanation": "x", "correction": "She has"},
        {"error_type": "单复数错误", "fragment": "many book", "explanation": "x", "correction": "many books"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder_two_rules)
        result = await save_notes(s, uid, None, "She have many book", errors, mock)
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
