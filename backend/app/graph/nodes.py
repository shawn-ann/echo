import json
from typing import Any

from app.graph.state import CorrectionState
from app.prompts.locate_prompt import build_locate_messages
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
