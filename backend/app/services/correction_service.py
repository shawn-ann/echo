import json
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.conversation import SessionConversation
from app.models.message import Message, MessageRole, MessageType
from app.models.report import CorrectionReport
from app.schemas.correction import LLMResponse, MessageOut
from app.services.llm_client import (
    LLMClient,
    LLMTimeoutError,
    LLMUnavailableError,
)

SYSTEM_PROMPT = (
    "你是英文纠错教练。根据对话上下文判断用户意图："
    "提交英文文本请判定为 correction 并输出结构化纠错报告；"
    "纯中文或提问请判定为 follow_up 并输出纯文本讲解。"
    "纠错报告遵循最小修正原则，报告内不重复展示原文；"
    "若无错误则 has_errors=false。必须输出合法 JSON，结构为 {intent, correction, reply}。"
)


async def get_or_create_conversation(session: AsyncSession, user_id: uuid.UUID) -> SessionConversation:
    conv = (
        await session.execute(
            select(SessionConversation)
            .where(SessionConversation.user_id == user_id)
            .order_by(SessionConversation.created_at)
            .limit(1)
        )
    ).scalars().first()
    if conv is not None:
        return conv
    conv = SessionConversation(user_id=user_id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def _fetch_reports(session: AsyncSession, report_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not report_ids:
        return {}
    rows = (
        await session.execute(select(CorrectionReport).where(CorrectionReport.id.in_(report_ids)))
    ).scalars().all()
    return {r.id: r.structure for r in rows}


async def build_context(session: AsyncSession, conversation_id: uuid.UUID, limit: int) -> list[dict]:
    rows = list(
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(limit)
            )
        ).scalars()
    )
    rows.reverse()
    reports = await _fetch_reports(session, [m.report_id for m in rows if m.report_id])
    result = []
    for m in rows:
        if m.type == MessageType.report and m.report_id in reports:
            content = json.dumps({"report": reports[m.report_id]}, ensure_ascii=False)
        else:
            content = m.content or ""
        result.append({"role": m.role.value, "content": content})
    return result


async def _call_and_parse(llm_client: LLMClient, messages: list[dict]) -> LLMResponse:
    for attempt in range(2):
        try:
            raw = await llm_client.complete(messages)
        except LLMTimeoutError:
            raise AppError(504, "LLM_TIMEOUT", "AI 响应超时，请重试")
        except LLMUnavailableError:
            raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务不可用，请稍后重试")
        try:
            return LLMResponse.model_validate_json(raw)
        except ValidationError:
            if attempt == 0:
                continue
            raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")
    raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_out(msg: Message, report: dict | None) -> MessageOut:
    return MessageOut(
        id=msg.id,
        role=msg.role.value,
        type=msg.type.value,
        content=msg.content,
        report=report,
        created_at=msg.created_at,
    )


async def submit_message(
    session: AsyncSession, user_id: uuid.UUID, content: str, llm_client: LLMClient
) -> tuple[MessageOut, MessageOut]:
    conv = await get_or_create_conversation(session, user_id)
    context = await build_context(session, conv.id, get_settings().CONTEXT_LIMIT)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *context,
        {"role": "user", "content": content},
    ]
    parsed = await _call_and_parse(llm_client, messages)

    user_created_at = _utcnow()
    user_type = MessageType.follow_up if parsed.intent == "follow_up" else MessageType.correction
    user_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.user,
        type=user_type,
        content=content,
        created_at=user_created_at,
    )
    session.add(user_msg)
    await session.flush()

    report_structure: dict | None = None
    if parsed.intent == "correction":
        if parsed.correction is None:
            raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")
        report_structure = parsed.correction.model_dump()
        report = CorrectionReport(version=1, structure=report_structure)
        session.add(report)
        await session.flush()
        ai_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.assistant,
            type=MessageType.report,
            content=None,
            report_id=report.id,
            created_at=user_created_at + timedelta(microseconds=1),
        )
        session.add(ai_msg)
        await session.flush()
        report.message_id = ai_msg.id
    else:
        ai_msg = Message(
            conversation_id=conv.id,
            role=MessageRole.assistant,
            type=MessageType.reply,
            content=parsed.reply,
            created_at=user_created_at + timedelta(microseconds=1),
        )
        session.add(ai_msg)
        await session.flush()

    await session.commit()
    return _to_out(user_msg, None), _to_out(ai_msg, report_structure)


async def list_messages(session: AsyncSession, user_id: uuid.UUID) -> list[MessageOut]:
    conv = await get_or_create_conversation(session, user_id)
    rows = list(
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at, Message.id)
            )
        ).scalars()
    )
    reports = await _fetch_reports(session, [m.report_id for m in rows if m.report_id])
    return [_to_out(m, reports.get(m.report_id)) for m in rows]
