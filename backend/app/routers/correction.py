from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
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
):
    rows = (
        await session.execute(
            select(Correction)
            .where(Correction.user_id == user.id)
            .order_by(Correction.created_at.asc())
        )
    ).scalars().all()
    return CorrectionsResponse(
        corrections=[CorrectionRecordOut.model_validate(row) for row in rows]
    )
