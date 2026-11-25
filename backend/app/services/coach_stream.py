"""Coach 流式链路：单次 LLM 调用 + 纠错 JSON / 追问纯文本双格式。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from pydantic import ValidationError

from app.prompts.coach_prompt import build_coach_messages
from app.schemas.coach import CoachCorrectReport, CoachCorrection, CoachReport
from app.services.coach_events import CoachEventMapper
from app.services.llm_client import LLMClient, get_llm_client
from app.services.partial_json import parse_partial

logger = logging.getLogger(__name__)

STREAM_TIMEOUT_SECONDS = 300
MAX_BUFFER_CHARS = 200_000
RAW_FALLBACK_CHARS = 20_000


class CoachBufferLimitError(Exception):
    pass


def format_sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def strip_code_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        else:
            text = text[3:]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()


def extract_json_object(raw: str) -> str:
    """提取第一个完整 JSON 对象，容忍模型在 JSON 前后多写一句话。"""
    text = strip_code_fence(raw)
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def validate_correction(raw: str) -> CoachCorrection | None:
    try:
        data = json.loads(extract_json_object(raw))
    except (json.JSONDecodeError, TypeError):
        return None
    try:
        return CoachCorrection.model_validate(data)
    except ValidationError:
        logger.warning("coach_correction_validation_failed raw_prefix=%s", raw[:300])
        return None


def _detect_mode(pending: str) -> tuple[str, str] | None:
    """根据首个非空白内容判断是纠错 JSON 还是纯文本回答。"""
    text = pending.lstrip()
    if not text:
        return None
    if text.startswith("```"):
        if "\n" not in text:
            return None
        rest = text.split("\n", 1)[1].lstrip()
        if not rest:
            return None
        return ("correct" if rest.startswith("{") else "answer", rest)
    return ("correct" if text.startswith("{") else "answer", text)


def _correction_report(correction: CoachCorrection) -> dict[str, Any]:
    return CoachCorrectReport(
        errors=correction.errors, rewrites=correction.rewrites
    ).model_dump(mode="json")


async def stream_coach_events(
    history: list[dict[str, str]],
    request: Request,
    client: LLMClient | None = None,
) -> AsyncIterator[str]:
    llm = client or get_llm_client()
    mapper = CoachEventMapper()
    mode: str | None = None
    pending = ""
    buffer = ""
    total_chars = 0

    try:
        async with asyncio.timeout(STREAM_TIMEOUT_SECONDS):
            # 纠错返回 JSON，追问返回纯文本，因此不能强制 response_format=json_object。
            async for chunk in llm.complete_stream(
                build_coach_messages(history),
                thinking=True,
                json_mode=False,
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

                if mode is None:
                    pending += text
                    detected = _detect_mode(pending)
                    if detected is None:
                        continue
                    mode, buffer = detected
                    for event, payload in mapper.force_mode(mode):
                        yield format_sse(event, payload)
                    if mode == "correct":
                        for event, payload in mapper.feed(parse_partial(buffer)):
                            yield format_sse(event, payload)
                    else:
                        yield format_sse("answer_delta", {"text": buffer})
                    continue

                buffer += text
                if mode == "correct":
                    for event, payload in mapper.feed(parse_partial(buffer)):
                        yield format_sse(event, payload)
                else:
                    yield format_sse("answer_delta", {"text": text})

        if await request.is_disconnected():
            return

        if mode == "correct":
            correction = validate_correction(buffer)
            if correction is not None:
                report = _correction_report(correction)
                for event, payload in mapper.feed_report(report):
                    yield format_sse(event, payload)
                yield format_sse("done", {"report": report})
            else:
                yield format_sse(
                    "done",
                    {
                        "report": None,
                        "raw": buffer[:RAW_FALLBACK_CHARS],
                    },
                )
        elif mode == "answer":
            answer = strip_code_fence(buffer)
            if not answer:
                yield format_sse("done", {"report": None, "raw": ""})
            else:
                yield format_sse(
                    "done", {"report": {"mode": "answer", "answer": answer}}
                )
        else:
            yield format_sse("done", {"report": None, "raw": ""})
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


__all__ = ["stream_coach_events", "validate_correction", "strip_code_fence", "CoachReport"]
