"""把 LangGraph 节点更新映射为稳定的 SSE 领域事件。"""

import json
from typing import Any

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
        if error:
            return [("rewrite_degraded", {"stage": "minimal", "message": str(error)})]
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
        if error:
            return [("rewrite_degraded", {"stage": "fluency", "message": str(error)})]
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
