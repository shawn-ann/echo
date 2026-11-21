"""把 LangGraph 节点更新映射为稳定的 SSE 领域事件。"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request

from app.graph.build import build_graph
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

NODE_EVENT: dict[str, str] = {
    "validate_errors": "errors",
    "minimal_edit": "minimal",
    "minimal_passthrough": "minimal",
    "native_fluency": "fluency",
}


def format_sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def events_from_update(node: str, update: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if node == "validate_errors":
        return [
            (
                "errors",
                {
                    "has_errors": bool(update.get("has_errors")),
                    "errors": update.get("errors") or [],
                },
            )
        ]

    if node in ("minimal_edit", "minimal_passthrough"):
        error = update.get("minimal_error")
        if error is not None:
            return [
                (
                    "rewrite_degraded",
                    {"stage": "minimal", "message": str(error) or "改写生成失败"},
                )
            ]
        return [
            (
                "minimal",
                {
                    "text": update.get("minimal_text", ""),
                    "note": update.get("minimal_note", ""),
                },
            )
        ]

    if node == "native_fluency":
        error = update.get("fluency_error")
        if error is not None:
            return [
                (
                    "rewrite_degraded",
                    {"stage": "fluency", "message": str(error) or "改写生成失败"},
                )
            ]
        return [
            (
                "fluency",
                {
                    "text": update.get("fluency_text", ""),
                    "note": update.get("fluency_note", ""),
                },
            )
        ]

    return []


async def stream_chat_events(
    text: str,
    client: LLMClient,
    request: Request,
) -> AsyncIterator[str]:
    if await request.is_disconnected():
        return

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
    graph = build_graph(client)
    request_id = uuid.uuid4().hex
    has_errors = False

    async def run() -> None:
        nonlocal has_errors
        try:
            async with asyncio.timeout(300):
                async for _mode, chunk in graph.astream(
                    {"text": text, "request_id": request_id},
                    stream_mode=["updates"],
                ):
                    for node, update in chunk.items():
                        if node == "validate_errors":
                            has_errors = bool(update.get("has_errors"))
                        for event, payload in events_from_update(node, update):
                            await queue.put((event, payload))
        except TimeoutError:
            await queue.put(
                ("error", {"code": "CHAT_STREAM_TIMEOUT", "message": "分析超时，请重试"})
            )
        except Exception:
            logger.exception("chat_stream_failed request_id=%s", request_id)
            await queue.put(
                (
                    "error",
                    {"code": "CHAT_STREAM_FAILED", "message": "AI 服务暂时不可用，请重试"},
                )
            )
        finally:
            await queue.put(("done", {"has_errors": has_errors}))
            await queue.put(None)

    task = asyncio.create_task(run())
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if item is None:
                break
            event, payload = item
            yield format_sse(event, payload)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
