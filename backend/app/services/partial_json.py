"""容错解析未闭合 JSON，供流式结构化输出使用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Partial:
    value: Any
    complete: bool


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.length = len(text)

    def parse(self) -> Partial | None:
        self._skip_ws()
        if self.pos >= self.length:
            return None
        return self._value()

    def _skip_ws(self) -> None:
        while self.pos < self.length and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < self.length else ""

    def _value(self) -> Partial | None:
        char = self._peek()
        if char == "{":
            return self._object()
        if char == "[":
            return self._array()
        if char == '"':
            return self._string()
        if char in "tfn":
            return self._literal()
        if char == "-" or char.isdigit():
            return self._number()
        return None

    def _literal(self) -> Partial:
        for word, value in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(word, self.pos):
                self.pos += len(word)
                return Partial(value, True)
            if word.startswith(self.text[self.pos:]):
                self.pos = self.length
                return Partial(value, False)
        self.pos = self.length
        return Partial(None, False)

    def _number(self) -> Partial:
        start = self.pos
        while self.pos < self.length and self.text[self.pos] in "-+.eE0123456789":
            self.pos += 1
        raw = self.text[start : self.pos]
        try:
            value = float(raw) if any(c in raw for c in ".eE") else int(raw)
        except ValueError:
            return Partial(raw, False)
        return Partial(value, True)

    def _string(self) -> Partial:
        # 跳过起始引号
        self.pos += 1
        chars: list[str] = []
        while self.pos < self.length:
            char = self.text[self.pos]
            if char == '"':
                self.pos += 1
                return Partial("".join(chars), True)
            if char == "\\":
                if self.pos + 1 >= self.length:
                    self.pos = self.length
                    return Partial("".join(chars), False)
                esc = self.text[self.pos + 1]
                if esc == "u":
                    if self.pos + 6 > self.length:
                        self.pos = self.length
                        return Partial("".join(chars), False)
                    code = self.text[self.pos + 2 : self.pos + 6]
                    try:
                        chars.append(chr(int(code, 16)))
                    except ValueError:
                        return Partial("".join(chars), False)
                    self.pos += 6
                    continue
                mapping = {
                    '"': '"',
                    "\\": "\\",
                    "/": "/",
                    "b": "\b",
                    "f": "\f",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }
                if esc not in mapping:
                    return Partial("".join(chars), False)
                chars.append(mapping[esc])
                self.pos += 2
                continue
            chars.append(char)
            self.pos += 1
        return Partial("".join(chars), False)

    def _object(self) -> Partial:
        self.pos += 1  # {
        result: dict[str, Any] = {}
        while True:
            self._skip_ws()
            if self.pos >= self.length:
                return Partial(result, False)
            if self._peek() == "}":
                self.pos += 1
                return Partial(result, True)
            if self._peek() != '"':
                return Partial(result, False)
            key = self._string()
            if not key.complete:
                return Partial(result, False)
            self._skip_ws()
            if self._peek() != ":":
                return Partial(result, False)
            self.pos += 1
            self._skip_ws()
            value = self._value()
            if value is None:
                return Partial(result, False)
            result[str(key.value)] = value
            if not value.complete:
                return Partial(result, False)
            self._skip_ws()
            char = self._peek()
            if char == ",":
                self.pos += 1
                continue
            if char == "}":
                self.pos += 1
                return Partial(result, True)
            return Partial(result, False)

    def _array(self) -> Partial:
        self.pos += 1  # [
        items: list[Partial] = []
        while True:
            self._skip_ws()
            if self.pos >= self.length:
                return Partial(items, False)
            if self._peek() == "]":
                self.pos += 1
                return Partial(items, True)
            value = self._value()
            if value is None:
                return Partial(items, False)
            if value.complete:
                items.append(value)
            self._skip_ws()
            char = self._peek()
            if char == ",":
                self.pos += 1
                continue
            if char == "]":
                self.pos += 1
                return Partial(items, True)
            return Partial(items, False)


def parse_partial(text: str) -> Partial | None:
    """解析可能未闭合的 JSON 文本。

    完整前缀会尽量解析出来；未闭合的字符串/对象/数组标记为 complete=False。
    """
    if not text or not text.strip():
        return None
    return _Parser(text).parse()


def wrap(value: Any) -> Partial:
    """把普通 Python 值包装成完整 Partial，便于复用同一套差分逻辑。"""
    if isinstance(value, dict):
        return Partial({key: wrap(item) for key, item in value.items()}, True)
    if isinstance(value, list):
        return Partial([wrap(item) for item in value], True)
    return Partial(value, True)
