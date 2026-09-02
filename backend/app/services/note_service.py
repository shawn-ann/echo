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
    NoteListItem,
    NoteLLMResponse,
    NoteRuleResult,
    UpdateNoteRequest,
)
from app.services.llm_client import LLMClient, LLMTimeoutError, LLMUnavailableError


async def _call_llm_and_parse(
    llm_client: LLMClient, source_text: str, errors: list[dict]
) -> NoteLLMResponse:
    messages = [
        {"role": "system", "content": build_note_system_prompt()},
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
    polished_sentence: str,
    errors: list[dict],
    llm_client: LLMClient,
) -> list[NoteRuleResult]:
    parsed = await _call_llm_and_parse(llm_client, source_text, errors)

    if source_message_id is not None and (await session.get(Message, source_message_id)) is None:
        source_message_id = None

    saved: list[NoteRuleResult] = []
    for result in parsed.results:
        note = Note(
            user_id=user_id,
            rule_title=result.rule_title,
            knowledge_point=result.knowledge_point,
            alternatives=result.alternatives,
            feynman_question=result.feynman_question,
        )
        session.add(note)
        await session.flush()

        inserted_any = False
        for case in result.cases:
            existing_case = (
                await session.execute(
                    select(NoteCase.id).where(
                        NoteCase.note_id == note.id,
                        NoteCase.user_id == user_id,
                        NoteCase.original_sentence == source_text,
                    )
                )
            ).scalars().first()
            if existing_case is not None:
                continue
            session.add(
                NoteCase(
                    note_id=note.id,
                    user_id=user_id,
                    original_sentence=source_text,
                    polished_sentence=polished_sentence,
                    change_details=case.change_details,
                    error_root=result.error_root,
                    source_message_id=source_message_id,
                )
            )
            note.updated_at = datetime.now(timezone.utc)
            inserted_any = True

        if not inserted_any:
            await session.delete(note)

        saved.append(result)

    await session.commit()
    return saved


async def list_notes(session: AsyncSession, user_id: uuid.UUID) -> list[NoteListItem]:
    rows = (
        await session.execute(
            select(
                Note.id,
                Note.rule_title,
                Note.knowledge_point,
                func.count(NoteCase.id).label("case_count"),
                Note.updated_at,
            )
            .join(NoteCase, NoteCase.note_id == Note.id)
            .where(NoteCase.user_id == user_id)
            .group_by(Note.id)
            .order_by(Note.updated_at.desc())
        )
    ).all()
    return [
        NoteListItem(
            id=r.id, rule_title=r.rule_title, knowledge_point=r.knowledge_point,
            case_count=r.case_count, updated_at=r.updated_at,
        )
        for r in rows
    ]


async def get_note_detail(
    session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID
) -> NoteDetailResponse | None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
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
        knowledge_point=note.knowledge_point,
        alternatives=note.alternatives,
        feynman_question=note.feynman_question,
        cases=[
            NoteCaseItem(
                id=c.id,
                original_sentence=c.original_sentence,
                polished_sentence=c.polished_sentence,
                change_details=c.change_details,
                error_root=c.error_root,
                created_at=c.created_at,
            )
            for c in cases
        ],
    )


async def delete_note(session: AsyncSession, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        return
    await session.delete(note)
    await session.commit()


async def delete_case(session: AsyncSession, user_id: uuid.UUID, case_id: uuid.UUID) -> None:
    case = await session.get(NoteCase, case_id)
    if case is None or case.user_id != user_id:
        return
    await session.delete(case)
    await session.commit()


async def update_note(
    session: AsyncSession,
    user_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: UpdateNoteRequest,
) -> NoteDetailResponse | None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        return None
    note.rule_title = payload.rule_title
    note.knowledge_point = payload.knowledge_point
    note.alternatives = payload.alternatives
    note.feynman_question = payload.feynman_question
    note.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(note)

    cases = (
        await session.execute(
            select(NoteCase)
            .where(NoteCase.note_id == note_id, NoteCase.user_id == user_id)
            .order_by(NoteCase.created_at)
        )
    ).scalars().all()
    return NoteDetailResponse(
        id=note.id,
        rule_title=note.rule_title,
        knowledge_point=note.knowledge_point,
        alternatives=note.alternatives,
        feynman_question=note.feynman_question,
        cases=[
            NoteCaseItem(
                id=c.id,
                original_sentence=c.original_sentence,
                polished_sentence=c.polished_sentence,
                change_details=c.change_details,
                error_root=c.error_root,
                created_at=c.created_at,
            )
            for c in cases
        ],
    )
