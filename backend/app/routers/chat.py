import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver

from app.graph.build import build_graph
from app.schemas.chat import ChatRequest
from app.services.chat_stream import stream_chat_events
from app.services.llm_client import get_llm_client

router = APIRouter(prefix="/api/v1", tags=["chat"])


def get_chat_graph(request: Request):
    graph = getattr(request.app.state, "chat_graph", None)
    if graph is None:
        graph = build_graph(get_llm_client(), MemorySaver())
        request.app.state.chat_graph = graph
    return graph


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    graph=Depends(get_chat_graph),
):
    thread_id = payload.thread_id or uuid.uuid4().hex
    return StreamingResponse(
        stream_chat_events(
            payload.content,
            graph,
            request,
            thread_id=thread_id,
            intent=payload.intent,
            turn_id=payload.turn_id,
            error_id=payload.error_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
