import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.message import Message
from app.models.note import Note, NoteCase
from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content
from app.schemas.note import (
    NoteCaseItem,
    NoteDetailResponse,
    NoteExample,
    NoteListItem,
    NoteLLMResponse,
    SavedNoteItem,
)
from app.services.llm_client import LLMClient, LLMTimeoutError, LLMUnavailableError


async def _get_existing_rule_titles(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(Note.rule_title))).scalars().all()
    return list(rows)


async def _call_llm_and_parse(
    llm_client: LLMClient, existing_rules: list[str], source_text: str, errors: list[dict]
) -> NoteLLMResponse:
    messages = [
        {"role": "system", "content": build_note_system_prompt(existing_rules)},
        {"role": "user", "content": build_note_user_content(source_text, errors)},
    ]
    for attempt in range(2):
        try:
            raw = await llm_client.complete(messages)
        except LLMTimeoutError:
            raise AppError(504, "LLM_TIMEOUT", "AI 响应超时，请重试")
        except LLMUnavailableError:
            raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务不可用，请稍后重试")
        try:
            return NoteLLMResponse.model_validate_json(raw)
        except ValidationError:
            pass
        if attempt == 0:
            continue
        raise AppError(502, "LLM_RESPONSE_INVALID", "AI 返回内容无效，请重试")
    raise AssertionError("unreachable")


async def save_notes(
    session: AsyncSession,
    user_id: uuid.UUID,
    source_message_id: uuid.UUID | None,
    source_text: str,
    errors: list[dict],
    llm_client: LLMClient,
) -> list[SavedNoteItem]:
    existing_rules = await _get_existing_rule_titles(session)
    parsed = await _call_llm_and_parse(llm_client, existing_rules, source_text, errors)

    # source_message_id 仅作溯源链接；若消息不存在则置空，避免外键违约
    if source_message_id is not None and (await session.get(Message, source_message_id)) is None:
        source_message_id = None

    # correction 由后端从 errors 匹配（取第一个匹配）
    errors_by_fragment: dict[str, str] = {}
    for e in errors:
        errors_by_fragment.setdefault(e["fragment"], e["correction"])

    saved: list[SavedNoteItem] = []
    for result in parsed.results:
        note = (
            await session.execute(select(Note).where(Note.rule_title == result.rule_title))
        ).scalars().first()
        if note is not None:
            is_new = False  # 已有规则：忽略 examples
        else:
            note = Note(
                rule_title=result.rule_title,
                description=result.description,
                examples=[ex.model_dump() for ex in result.examples],
            )
            session.add(note)
            await session.flush()
            is_new = True

        inserted_any = False  # 新增：跟踪是否插入案例
        for fragment in result.references:
            correction = errors_by_fragment.get(fragment)
            if not correction:
                continue  # 防御：LLM 归组了不在 errors 中的文本

            # 先查重：同 (note, user, source_text, fragment) 已存在则跳过
            existing_case = (
                await session.execute(
                    select(NoteCase.id).where(
                        NoteCase.note_id == note.id,
                        NoteCase.user_id == user_id,
                        NoteCase.source_text == source_text,
                        NoteCase.fragment == fragment,
                    )
                )
            ).scalars().first()
            if existing_case is not None:
                continue  # 重复案例，静默跳过

            case = NoteCase(
                note_id=note.id,
                user_id=user_id,
                fragment=fragment,
                correction=correction,
                source_text=source_text,
                source_message_id=source_message_id,
            )
            session.add(case)
            await session.flush()
            note.updated_at = datetime.now(timezone.utc)
            inserted_any = True  # 新增
            saved.append(SavedNoteItem(note_id=note.id, rule_title=note.rule_title, is_new=is_new, case_id=case.id))

        # 新增：新建规则但无案例入账 → 删除孤立 Note
        if is_new and not inserted_any:
            await session.delete(note)

    await session.commit()
    return saved


async def list_notes(session: AsyncSession, user_id: uuid.UUID) -> list[NoteListItem]:
    rows = (
        await session.execute(
            select(
                Note.id,
                Note.rule_title,
                Note.description,
                func.count(NoteCase.id).label("case_count"),
                Note.updated_at,
                func.max(NoteCase.created_at).label("last_case_at"),
            )
            .join(NoteCase, NoteCase.note_id == Note.id)
            .where(NoteCase.user_id == user_id)
            .group_by(Note.id)
            .order_by(func.max(NoteCase.created_at).desc())
        )
    ).all()
    return [
        NoteListItem(
            id=r.id, rule_title=r.rule_title, description=r.description,
            case_count=r.case_count, updated_at=r.updated_at,
        )
        for r in rows
    ]


async def get_note_detail(
    session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID
) -> NoteDetailResponse | None:
    note = await session.get(Note, note_id)
    if note is None:
        return None
    cases = (
        await session.execute(
            select(NoteCase)
            .where(NoteCase.note_id == note_id, NoteCase.user_id == user_id)
            .order_by(NoteCase.created_at)
        )
    ).scalars().all()
    if not cases:
        return None
    return NoteDetailResponse(
        id=note.id,
        rule_title=note.rule_title,
        description=note.description,
        examples=[NoteExample.model_validate(ex) for ex in note.examples],
        cases=[
            NoteCaseItem(
                id=c.id, fragment=c.fragment, correction=c.correction,
                source_text=c.source_text, created_at=c.created_at,
            )
            for c in cases
        ],
    )


async def delete_note(session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
    cases = (
        await session.execute(
            select(NoteCase).where(NoteCase.note_id == note_id, NoteCase.user_id == user_id)
        )
    ).scalars().all()
    for c in cases:
        await session.delete(c)
    await session.commit()


async def delete_case(session: AsyncSession, user_id: uuid.UUID, case_id: uuid.UUID) -> None:
    case = await session.get(NoteCase, case_id)
    if case is None or case.user_id != user_id:
        return
    await session.delete(case)
    await session.commit()
