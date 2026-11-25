"""把增量 JSON 差分映射成稳定的 SSE 领域事件。"""

from __future__ import annotations

from typing import Any

from app.services.partial_json import Partial, wrap

SCHEMA_VERSION = 1
REWRITE_VARIANTS = ("formal", "casual", "minimal")


def _str(node: Partial | None) -> str | None:
    if node is None or not node.complete or not isinstance(node.value, str):
        return None
    return node.value


class CoachEventMapper:
    """幂等差分器：同一份数据可多次 feed，只发新增且已闭合的内容。"""

    def __init__(self) -> None:
        self.mode: str | None = None
        self._mode_emitted = False
        self._errors_emitted = 0
        self._rewrites_emitted: set[str] = set()
        self._answer_length = 0

    def feed(self, partial: Partial | None) -> list[tuple[str, dict[str, Any]]]:
        if partial is None or not isinstance(partial.value, dict):
            return []

        events = self._emit_mode(partial)
        if not self._mode_emitted:
            return events
        if self.mode == "correct":
            events += self._emit_errors(partial)
            events += self._emit_rewrites(partial)
        elif self.mode == "answer":
            events += self._emit_answer(partial)
        return events

    def force_mode(self, mode: str) -> list[tuple[str, dict[str, Any]]]:
        """输出里没有 mode 时，由服务端按首个字段推导并补发 report_start。"""
        if self._mode_emitted or mode not in ("correct", "answer"):
            return []
        self.mode = mode
        self._mode_emitted = True
        return [("report_start", {"schema_version": SCHEMA_VERSION, "mode": mode})]

    def feed_report(self, report: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """用校验后的完整报告做最后一次差分，补齐漏掉的条目。"""
        return self.feed(wrap(report))

    def _emit_mode(self, partial: Partial) -> list[tuple[str, dict[str, Any]]]:
        if self._mode_emitted:
            return []
        mode = _str(partial.value.get("mode"))
        if mode not in ("correct", "answer"):
            return []
        self.mode = mode
        self._mode_emitted = True
        return [("report_start", {"schema_version": SCHEMA_VERSION, "mode": mode})]

    def _emit_errors(self, partial: Partial) -> list[tuple[str, dict[str, Any]]]:
        events: list[tuple[str, dict[str, Any]]] = []
        node = partial.value.get("errors")
        if node is None or not isinstance(node.value, list):
            return events
        for index, item in enumerate(node.value):
            if index < self._errors_emitted:
                continue
            if not item.complete or not isinstance(item.value, dict):
                break
            values = {key: _str(item.value.get(key)) for key in ("severity", "fragment", "type", "reason", "fix")}
            if any(value is None for value in values.values()):
                break
            events.append(("error_added", {"index": index, **values}))
            self._errors_emitted = index + 1
        return events

    def _emit_rewrites(self, partial: Partial) -> list[tuple[str, dict[str, Any]]]:
        events: list[tuple[str, dict[str, Any]]] = []
        node = partial.value.get("rewrites")
        if node is None or not isinstance(node.value, dict):
            return events
        for variant in REWRITE_VARIANTS:
            if variant in self._rewrites_emitted:
                continue
            item = node.value.get(variant)
            if item is None or not item.complete or not isinstance(item.value, dict):
                continue
            text = _str(item.value.get("text"))
            if text is None:
                continue
            payload: dict[str, Any] = {"variant": variant, "text": text}
            note = _str(item.value.get("note"))
            if note:
                payload["note"] = note
            events.append(("rewrite_ready", payload))
            self._rewrites_emitted.add(variant)
        return events

    def _emit_answer(self, partial: Partial) -> list[tuple[str, dict[str, Any]]]:
        text = _str(partial.value.get("answer"))
        if text is None or len(text) <= self._answer_length:
            return []
        delta = text[self._answer_length :]
        self._answer_length = len(text)
        return [("answer_delta", {"text": delta})]
