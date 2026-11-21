from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.services.chat_stream import stream_chat_events
from app.services.llm_client import LLMClient, get_llm_client

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    client: LLMClient = Depends(get_llm_client),
):
    return StreamingResponse(
        stream_chat_events(payload.content, client, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
