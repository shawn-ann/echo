import json
from typing import Any, Literal

from app.graph.state import CorrectionState
from app.prompts.locate_prompt import build_locate_messages
from app.prompts.rewrite_prompt import build_fluency_messages, build_minimal_messages
from app.services.error_validation import validate_errors
from app.services.llm_client import LLMClient


class LocateError(Exception):
    """定位节点在重试后仍无法返回可解析的错误列表。"""


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def make_locate_node(client: LLMClient):
    async def locate(state: CorrectionState) -> dict[str, Any]:
        messages = build_locate_messages(state["text"])
        last_error: Exception | None = None
        for _ in range(2):
            raw = await client.complete(messages, thinking=True, json_mode=True)
            try:
                data = parse_json_object(raw)
                errors = data.get("errors")
                if not isinstance(errors, list):
                    raise ValueError("errors must be a list")
                return {"raw_errors": errors}
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                continue
        raise LocateError(str(last_error))

    return locate


def validate_errors_node(state: CorrectionState) -> dict[str, Any]:
    errors = validate_errors(
        state.get("raw_errors") or [],
        state["text"],
        request_id=state.get("request_id", "-"),
    )
    return {"errors": errors, "has_errors": bool(errors)}


def _parse_rewrite(raw: str) -> dict[str, str]:
    data = parse_json_object(raw)
    text = data.get("text")
    note = data.get("note")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("rewrite.text must be a non-empty string")
    if not isinstance(note, str):
        raise ValueError("rewrite.note must be a string")
    return {"text": text, "note": note}


def make_minimal_node(client: LLMClient):
    async def minimal(state: CorrectionState) -> dict[str, Any]:
        try:
            raw = await client.complete(
                build_minimal_messages(state["text"], state.get("errors") or []),
                thinking=False,
                json_mode=True,
            )
            parsed = _parse_rewrite(raw)
            return {
                "minimal_text": parsed["text"],
                "minimal_note": parsed["note"],
                "minimal_error": None,
            }
        except Exception as exc:
            return {"minimal_text": "", "minimal_note": "", "minimal_error": str(exc)}

    return minimal


def make_fluency_node(client: LLMClient):
    async def fluency(state: CorrectionState) -> dict[str, Any]:
        try:
            raw = await client.complete(
                build_fluency_messages(state["text"], state.get("errors") or []),
                thinking=False,
                json_mode=True,
            )
            parsed = _parse_rewrite(raw)
            return {
                "fluency_text": parsed["text"],
                "fluency_note": parsed["note"],
                "fluency_error": None,
            }
        except Exception as exc:
            return {"fluency_text": "", "fluency_note": "", "fluency_error": str(exc)}

    return fluency


def minimal_passthrough_node(state: CorrectionState) -> dict[str, Any]:
    return {
        "minimal_text": state["text"],
        "minimal_note": "原文未发现语法错误，保持原样",
        "minimal_error": None,
    }


def route_after_validate(state: CorrectionState) -> Literal["minimal_edit", "minimal_passthrough"]:
    return "minimal_edit" if state.get("has_errors") else "minimal_passthrough"
