from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.models.user import User
from app.schemas.correction_stream import CorrectionStreamRequest
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
