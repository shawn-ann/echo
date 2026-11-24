from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.coach import CoachRequest
from app.services.coach_stream import stream_coach_events

router = APIRouter(prefix="/api/v1", tags=["coach"])


@router.post("/coach/stream")
async def coach_stream(payload: CoachRequest, request: Request):
    history = [{"role": m.role, "content": m.content} for m in payload.messages]
    return StreamingResponse(
        stream_coach_events(history, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
