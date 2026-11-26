"""单条纠错流式链路：一次 LLM 调用，严格 JSON 输出。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request

from app.prompts.coach_prompt import COACH_SYSTEM_PROMPT
from app.schemas.coach import CoachCorrectReport
from app.services.coach_events import CoachEventMapper
from app.services.coach_stream import (
    MAX_BUFFER_CHARS,
    RAW_FALLBACK_CHARS,
    STREAM_TIMEOUT_SECONDS,
    CoachBufferLimitError,
    format_sse,
    validate_correction,
)
from app.services.llm_client import LLMClient, get_llm_client
from app.services.partial_json import parse_partial

logger = logging.getLogger(__name__)


def build_correction_messages(content: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COACH_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


async def stream_correction_events(
    content: str,
    request: Request,
    client: LLMClient | None = None,
) -> AsyncIterator[str]:
    llm = client or get_llm_client()
    mapper = CoachEventMapper()
    chunks: list[str] = []
    total_chars = 0
    started = False

    try:
        async with asyncio.timeout(STREAM_TIMEOUT_SECONDS):
            async for chunk in llm.complete_stream(
                build_correction_messages(content),
                thinking=True,
                json_mode=True,
                reasoning_effort="high",
            ):
                if await request.is_disconnected():
                    return
                kind = chunk.get("type")
                text = chunk.get("text") or ""
                if not text:
                    continue
                if kind == "reasoning":
                    yield format_sse("reasoning", {"text": text})
                    continue

                if not started:
                    started = True
                    for event, payload in mapper.force_mode("correct"):
                        yield format_sse(event, payload)

                total_chars += len(text)
                if total_chars > MAX_BUFFER_CHARS:
                    raise CoachBufferLimitError
                chunks.append(text)
                for event, payload in mapper.feed(parse_partial("".join(chunks))):
                    yield format_sse(event, payload)

        if await request.is_disconnected():
            return

        raw = "".join(chunks)
        correction = validate_correction(raw)
        if correction is None:
            yield format_sse(
                "done", {"report": None, "raw": raw[:RAW_FALLBACK_CHARS]}
            )
            return

        report = CoachCorrectReport(
            errors=correction.errors, rewrites=correction.rewrites
        ).model_dump(mode="json")
        for event, payload in mapper.feed_report(report):
            yield format_sse(event, payload)
        yield format_sse("done", {"report": report})
    except TimeoutError:
        yield format_sse(
            "error", {"code": "CORRECTION_STREAM_TIMEOUT", "message": "分析超时，请重试"}
        )
    except CoachBufferLimitError:
        yield format_sse(
            "error",
            {"code": "CORRECTION_BUFFER_LIMIT", "message": "输出过长，请缩短输入后重试"},
        )
    except Exception:
        logger.exception("correction_stream_failed")
        yield format_sse(
            "error",
            {
                "code": "CORRECTION_STREAM_FAILED",
                "message": "AI 服务暂时不可用，请重试",
            },
        )
