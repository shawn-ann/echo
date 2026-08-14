import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.errors import AppError
from app.db import async_session_factory
from app.models.message import Message
from app.models.report import CorrectionReport
from app.models.user import User
from app.services.correction_service import (
    build_context,
    get_or_create_conversation,
    list_messages,
    submit_message,
)
from app.services.llm_client import (
    LLMTimeoutError,
    LLMUnavailableError,
    MockLLMClient,
)


async def _demo_user_id() -> uuid.UUID:
    async with async_session_factory() as s:
        user = (await s.execute(select(User).where(User.username == "demo"))).scalar_one()
        return user.id


async def _count(model):
    async with async_session_factory() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()


async def test_get_or_create_conversation_is_singleton():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        c1 = await get_or_create_conversation(s, uid)
        c2 = await get_or_create_conversation(s, uid)
        assert c1.id == c2.id


async def test_submit_correction_writes_message_pair_and_report():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        user_out, ai_out = await submit_message(
            s, uid, "Yesterday I go to the park", mock
        )
        assert user_out.type == "correction"
        assert ai_out.type == "report"
        assert ai_out.report["has_errors"] is True
    assert await _count(Message) == 2
    assert await _count(CorrectionReport) == 1


async def test_submit_chinese_still_returns_report():
    # 单轮纠错：纯中文输入也返回纠错报告（不再有 follow_up/reply）
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        user_out, ai_out = await submit_message(s, uid, "为什么不能用 very？", mock)
        assert user_out.type == "correction"
        assert ai_out.type == "report"
        assert ai_out.report["has_errors"] is True


async def test_build_context_includes_report_structure():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        await submit_message(s, uid, "Yesterday I go to the park", mock)
        conv = await get_or_create_conversation(s, uid)
        ctx = await build_context(s, conv.id, get_settings().CONTEXT_LIMIT)
        assert len(ctx) == 2
        assert "report" in ctx[1]["content"]


async def test_list_messages_orders_and_embeds_report():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = MockLLMClient()
        await submit_message(s, uid, "Yesterday I go to the park", mock)
        msgs = await list_messages(s, uid)
        assert [m.type for m in msgs] == ["correction", "report"]
        assert msgs[1].report["has_errors"] is True


class _RaisingLLMClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def complete(self, messages: list[dict]) -> str:
        raise self._exc


async def test_submit_timeout_raises_504():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMTimeoutError())
        with pytest.raises(AppError) as exc_info:
            await submit_message(s, uid, "hello world", mock)
        assert exc_info.value.status_code == 504
        assert exc_info.value.code == "LLM_TIMEOUT"


async def test_submit_llm_unavailable_raises_503():
    uid = await _demo_user_id()
    async with async_session_factory() as s:
        mock = _RaisingLLMClient(LLMUnavailableError())
        with pytest.raises(AppError) as exc_info:
            await submit_message(s, uid, "hello world", mock)
        assert exc_info.value.status_code == 503
        assert exc_info.value.code == "LLM_SERVICE_UNAVAILABLE"
