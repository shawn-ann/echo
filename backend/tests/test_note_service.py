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


def _mock_responder(msgs):
    return json.dumps({
        "results": [{
            "rule_title": "第三人称单数主谓一致",
            "knowledge_point": "一般现在时中，第三人称单数主语动词加 -s/-es",
            "warning": "你常忘给 she/he/it 加 -s",
            "alternatives": ["She runs.", "He goes."],
            "feynman_question": "主语是 she/he/it 时动词怎么变？",
            "error_root": "主谓不一致",
            "cases": [{"change_details": "She go → She goes; He go → He goes"}],
        }]
    }, ensure_ascii=False)


async def test_save_creates_note_with_8field_and_case():
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"},
        {"error_type": "主谓不一致", "fragment": "He go", "explanation": "x", "correction": "He goes"},
    ]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder)
        result = await save_notes(s, uid, None, "She go to school. He go home.", "She goes to school. He goes home.", errors, mock)
        assert len(result) == 1

    async with async_session_factory() as s:
        note = (await s.execute(select(Note).where(Note.rule_title == "第三人称单数主谓一致"))).scalar_one()
        assert note.user_id == uid
        assert note.knowledge_point == "一般现在时中，第三人称单数主语动词加 -s/-es"
        assert note.warning == "你常忘给 she/he/it 加 -s"
        assert note.alternatives == ["She runs.", "He goes."]
        assert note.feynman_question == "主语是 she/he/it 时动词怎么变？"
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
        assert len(cases) == 1
        case = cases[0]
        assert case.original_sentence == "She go to school. He go home."
        assert case.polished_sentence == "She goes to school. He goes home."
        assert case.change_details == "She go → She goes; He go → He goes"
        assert case.error_root == "主谓不一致"


async def test_save_group_by_error_type_creates_multiple_notes():
    """不同 error_type 生成多条笔记"""
    uid = await _demo_user_id()
    errors = [
        {"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"},
        {"error_type": "冠词缺失", "fragment": "a apple", "explanation": "x", "correction": "an apple"},
    ]
    responder = lambda msgs: json.dumps({
        "results": [
            {
                "rule_title": "主谓一致规则", "knowledge_point": "kp", "warning": "w",
                "alternatives": ["A"], "feynman_question": "q", "error_root": "主谓不一致",
                "cases": [{"change_details": "She go → She goes"}],
            },
            {
                "rule_title": "元音音素前用 an", "knowledge_point": "kp2", "warning": "w2",
                "alternatives": ["B"], "feynman_question": "q2", "error_root": "冠词缺失",
                "cases": [{"change_details": "a apple → an apple"}],
            },
        ]
    }, ensure_ascii=False)
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=responder)
        result = await save_notes(s, uid, None, "She go to school and eat a apple", "She goes to school and eats an apple", errors, mock)
        assert len(result) == 2
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note).where(Note.user_id == uid))).scalars().all()
        assert len(notes) == 2
        roots = {c.error_root for n in notes for c in (await s.execute(select(NoteCase).where(NoteCase.note_id == n.id))).scalars().all()}
        assert roots == {"主谓不一致", "冠词缺失"}


async def test_save_same_rule_title_creates_separate_notes():
    """同 user、同 rule_title 连续两次 save，每次新建独立 Note，各 1 个 case"""
    uid = await _demo_user_id()
    errors1 = [{"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"}]
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder)
        await save_notes(s, uid, None, "She go to school.", "She goes to school.", errors1, mock)
    async with async_session_factory() as s:
        mock2 = MockLLMClient(responder=_mock_responder)
        result = await save_notes(s, uid, None, "He go home.", "He goes home.", errors1, mock2)
        assert len(result) == 1
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note).where(Note.user_id == uid, Note.rule_title == "第三人称单数主谓一致"))).scalars().all()
        assert len(notes) == 2
        for note in notes:
            assert note.knowledge_point == "一般现在时中，第三人称单数主语动词加 -s/-es"
            assert note.warning == "你常忘给 she/he/it 加 -s"
            assert note.alternatives == ["She runs.", "He goes."]
            assert note.feynman_question == "主语是 she/he/it 时动词怎么变？"
            cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == note.id))).scalars().all()
            assert len(cases) == 1


async def test_save_duplicate_cases_in_one_result_skipped():
    """单个 result 内重复 change_details 的 case（同 note_id + 同 original_sentence）被跳过，只插 1 个 case"""
    uid = await _demo_user_id()
    errors = [{"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"}]
    responder = lambda msgs: json.dumps({
        "results": [{
            "rule_title": "重复案例规则", "knowledge_point": "kp", "warning": "w",
            "alternatives": ["A"], "feynman_question": "q", "error_root": "主谓不一致",
            "cases": [
                {"change_details": "She go → She goes"},
                {"change_details": "She go → She goes"},
            ],
        }]
    }, ensure_ascii=False)
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=responder)
        result = await save_notes(s, uid, None, "She go to school.", "She goes to school.", errors, mock)
        assert len(result) == 1
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note).where(Note.rule_title == "重复案例规则"))).scalars().all()
        assert len(notes) == 1
        cases = (await s.execute(select(NoteCase).where(NoteCase.note_id == notes[0].id))).scalars().all()
        assert len(cases) == 1


async def test_save_empty_cases_deletes_orphan_note():
    """LLM 返回 cases 为空的 result 时，不留下无案例的孤立 Note"""
    uid = await _demo_user_id()
    errors = [{"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"}]
    responder = lambda msgs: json.dumps({
        "results": [{
            "rule_title": "空案例规则", "knowledge_point": "kp", "warning": "w",
            "alternatives": ["A"], "feynman_question": "q", "error_root": "主谓不一致",
            "cases": [],
        }]
    }, ensure_ascii=False)
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=responder)
        result = await save_notes(s, uid, None, "She go to school.", "She goes to school.", errors, mock)
        assert len(result) == 1
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note).where(Note.rule_title == "空案例规则"))).scalars().all()
        assert notes == []


async def test_save_different_user_creates_separate_note():
    """不同用户的同 rule_title 是独立笔记"""
    uid1 = await _demo_user_id()
    async with async_session_factory() as s:
        from app.core.security import hash_password
        from app.models.user import User, UserStatus
        s.add(User(username="other_u", password_hash=hash_password("other1234"), status=UserStatus.active))
        await s.commit()
        uid2 = (await s.execute(select(User).where(User.username == "other_u"))).scalar_one().id
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=_mock_responder)
        await save_notes(s, uid1, None, "She go to school.", "She goes to school.", [{"error_type": "主谓不一致", "fragment": "She go", "explanation": "x", "correction": "She goes"}], mock)
        await save_notes(s, uid2, None, "He go home.", "He goes home.", [{"error_type": "主谓不一致", "fragment": "He go", "explanation": "x", "correction": "He goes"}], mock)
    async with async_session_factory() as s:
        notes = (await s.execute(select(Note))).scalars().all()
        assert len(notes) == 2
        assert {n.user_id for n in notes} == {uid1, uid2}


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
            await save_notes(s, uid, None, "x", "y", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 504


async def test_save_llm_unavailable_raises_503():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMUnavailableError())
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", "y", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 503


async def test_save_invalid_llm_response_raises_502():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient(responder=lambda msgs: "not-json")
        with pytest.raises(AppError) as exc_info:
            await save_notes(s, uid, None, "x", "y", [{"error_type": "t", "fragment": "f", "explanation": "e", "correction": "c"}], mock)
        assert exc_info.value.status_code == 502
