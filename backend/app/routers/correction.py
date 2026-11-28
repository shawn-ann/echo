import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.correction import Correction

from app.models.user import User
from app.schemas.correction_stream import (
    CorrectionRecordOut,
    CorrectionsResponse,
    CorrectionStreamRequest,
)
from app.services.auth_service import get_current_user
from app.services.correction_stream import stream_correction_events

router = APIRouter(prefix="/api/v1", tags=["correction"])

CURSOR_VERSION = 1


def _encode_cursor(created_at: datetime, record_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{record_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(padded.encode()).decode()
    created_at, record_id = raw.split("|", 1)
    return datetime.fromisoformat(created_at), uuid.UUID(record_id)


@router.post("/correction/stream")
async def correction_stream(
    payload: CorrectionStreamRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    return StreamingResponse(
        stream_correction_events(
            payload.content,
            request,
            user_id=user.id,
            mode=payload.mode,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/corrections", response_model=CorrectionsResponse)
async def list_corrections(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
    before: str | None = Query(default=None),
):
    stmt = select(Correction).where(Correction.user_id == user.id)
    if before:
        cursor_created_at, cursor_id = _decode_cursor(before)
        stmt = stmt.where(
            or_(
                Correction.created_at < cursor_created_at,
                and_(
                    Correction.created_at == cursor_created_at,
                    Correction.id < cursor_id,
                ),
            )
        )
    rows = list(
        (
            await session.execute(
                stmt.order_by(Correction.created_at.desc(), Correction.id.desc()).limit(
                    limit + 1
                )
            )
        ).scalars()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = _encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return CorrectionsResponse(
        corrections=[CorrectionRecordOut.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
