"""Coach 流式链路：单次 LLM 调用 + 增量 JSON 差分事件。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from pydantic import TypeAdapter, ValidationError

from app.prompts.coach_prompt import build_coach_messages
from app.schemas.coach import CoachReport
from app.services.coach_events import CoachEventMapper
from app.services.llm_client import LLMClient, get_llm_client
from app.services.partial_json import parse_partial

logger = logging.getLogger(__name__)

STREAM_TIMEOUT_SECONDS = 300
MAX_BUFFER_CHARS = 200_000
RAW_FALLBACK_CHARS = 20_000

_report_adapter: TypeAdapter[CoachReport] = TypeAdapter(CoachReport)


class CoachBufferLimitError(Exception):
    pass


def format_sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def validate_report(raw: str) -> CoachReport | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    try:
        return _report_adapter.validate_python(data)
    except ValidationError:
        logger.warning("coach_report_validation_failed raw_prefix=%s", raw[:300])
        return None


async def stream_coach_events(
    history: list[dict[str, str]],
    request: Request,
    client: LLMClient | None = None,
) -> AsyncIterator[str]:
    llm = client or get_llm_client()
    mapper = CoachEventMapper()
    chunks: list[str] = []
    total_chars = 0

    try:
        async with asyncio.timeout(STREAM_TIMEOUT_SECONDS):
            async for chunk in llm.complete_stream(
                build_coach_messages(history),
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
                total_chars += len(text)
                if total_chars > MAX_BUFFER_CHARS:
                    raise CoachBufferLimitError
                chunks.append(text)
                partial = parse_partial("".join(chunks))
                for event, payload in mapper.feed(partial):
                    yield format_sse(event, payload)

        if await request.is_disconnected():
            return

        raw = "".join(chunks)
        report = validate_report(raw)
        if report is not None:
            report_data = report.model_dump(mode="json")
            # 最后一次全量差分，补齐流式期间漏发的条目。
            for event, payload in mapper.feed_report(report_data):
                yield format_sse(event, payload)
            yield format_sse("done", {"report": report_data})
        else:
            yield format_sse(
                "done",
                {"report": None, "raw": raw[:RAW_FALLBACK_CHARS]},
            )
    except TimeoutError:
        yield format_sse(
            "error", {"code": "COACH_STREAM_TIMEOUT", "message": "分析超时，请重试"}
        )
    except CoachBufferLimitError:
        yield format_sse(
            "error",
            {"code": "COACH_BUFFER_LIMIT", "message": "输出过长，请缩短输入后重试"},
        )
    except Exception:
        logger.exception("coach_stream_failed")
        yield format_sse(
            "error",
            {
                "code": "COACH_STREAM_FAILED",
                "message": "AI 服务暂时不可用，请重试",
            },
        )
