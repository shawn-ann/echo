import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db import get_db
from app.models.user import User
from app.schemas.note import (
    NoteDetailResponse,
    NoteListResponse,
    UpdateNoteRequest,
)
from app.services import note_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


@router.get("", response_model=NoteListResponse)
async def list_notes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    notes = await note_service.list_notes(session, user.id)
    return NoteListResponse(notes=notes)


@router.get("/{note_id}", response_model=NoteDetailResponse)
async def get_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    detail = await note_service.get_note_detail(session, user.id, note_id)
    if detail is None:
        raise AppError(404, "NOTE_NOT_FOUND", "笔记不存在")
    return detail


@router.put("/{note_id}", response_model=NoteDetailResponse)
async def update_note(
    note_id: uuid.UUID,
    payload: UpdateNoteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    detail = await note_service.update_note(session, user.id, note_id, payload)
    if detail is None:
        raise AppError(404, "NOTE_NOT_FOUND", "笔记不存在")
    return detail


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await note_service.delete_note(session, user.id, note_id)
    return None


@router.delete("/{note_id}/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    note_id: uuid.UUID,
    case_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await note_service.delete_case(session, user.id, case_id)
    return None
