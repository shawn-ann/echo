from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.correction_stream import CorrectionStreamRequest
from app.services.correction_stream import stream_correction_events

router = APIRouter(prefix="/api/v1", tags=["correction"])


@router.post("/correction/stream")
async def correction_stream(payload: CorrectionStreamRequest, request: Request):
    return StreamingResponse(
        stream_correction_events(payload.content, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
