import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.note import Note, NoteCase
from app.prompts.note_prompt import build_note_system_prompt, build_note_user_content
from app.schemas.note import NoteLLMResponse, SavedNoteItem
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

    saved: list[SavedNoteItem] = []
    for result in parsed.results:
        note = (
            await session.execute(select(Note).where(Note.rule_title == result.rule_title))
        ).scalars().first()
        if note is not None:
            case = NoteCase(
                note_id=note.id,
                user_id=user_id,
                example=result.example,
                source_text=source_text,
                source_message_id=source_message_id,
            )
            session.add(case)
            await session.flush()
            saved.append(SavedNoteItem(note_id=note.id, rule_title=note.rule_title, is_new=False, case_id=case.id))
        else:
            note = Note(rule_title=result.rule_title, description=result.description)
            session.add(note)
            await session.flush()
            case = NoteCase(
                note_id=note.id,
                user_id=user_id,
                example=result.example,
                source_text=source_text,
                source_message_id=source_message_id,
            )
            session.add(case)
            await session.flush()
            saved.append(SavedNoteItem(note_id=note.id, rule_title=note.rule_title, is_new=True, case_id=case.id))

    await session.commit()
    return saved
