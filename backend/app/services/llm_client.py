import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


class LLMClient:
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool = True,
        json_mode: bool = True,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> str:
        raise NotImplementedError

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool = True,
        json_mode: bool = True,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        """按增量产出 {"type": "reasoning"|"content", "text": ...}。"""
        raise NotImplementedError
        yield {}  # pragma: no cover - 让类型层面成为 async generator


class LLMTimeoutError(Exception):
    pass


class LLMUnavailableError(Exception):
    pass


class RealLLMClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        thinking_param: str = "chat_template_kwargs",
        thinking_always_on: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._transport = transport
        self.thinking_param = thinking_param
        self.thinking_always_on = thinking_always_on

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool = True,
        json_mode: bool = True,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> str:
        effective_thinking = True if self.thinking_always_on else thinking
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            # temperature 不注入，交由服务端默认值
        }
        if self.thinking_param == "enable_thinking":
            payload["enable_thinking"] = effective_thinking
        elif self.thinking_param == "thinking":
            payload["thinking"] = {
                "type": "enabled" if effective_thinking else "disabled"
            }
        else:
            payload["chat_template_kwargs"] = {"enable_thinking": effective_thinking}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        if temperature is not None:
            payload["temperature"] = temperature

        last_exc: Exception | None = None
        for _attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120, transport=self._transport) as client:
                    r = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
            except httpx.TimeoutException as exc:
                last_exc = exc
                continue
            except httpx.HTTPError as exc:
                last_exc = exc
                continue
        if isinstance(last_exc, httpx.TimeoutException):
            raise LLMTimeoutError from last_exc
        raise LLMUnavailableError from last_exc

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool = True,
        json_mode: bool = True,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        payload = self._build_payload(
            messages,
            thinking=thinking,
            json_mode=json_mode,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
        )
        payload["stream"] = True
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0), transport=self._transport
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise LLMUnavailableError(
                            f"LLM returned status {response.status_code}"
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            obj = json.loads(data)
                            delta = obj["choices"][0].get("delta") or {}
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue
                        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                        if reasoning:
                            yield {"type": "reasoning", "text": str(reasoning)}
                        content = delta.get("content")
                        if content:
                            yield {"type": "content", "text": str(content)}
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError from exc

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool,
        json_mode: bool,
        reasoning_effort: str | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        effective_thinking = True if self.thinking_always_on else thinking
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            # temperature 不注入，交由服务端默认值
        }
        if self.thinking_param == "enable_thinking":
            payload["enable_thinking"] = effective_thinking
        elif self.thinking_param == "thinking":
            payload["thinking"] = {
                "type": "enabled" if effective_thinking else "disabled"
            }
        else:
            payload["chat_template_kwargs"] = {"enable_thinking": effective_thinking}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        if temperature is not None:
            payload["temperature"] = temperature
        return payload


def _default_responder(messages: list[dict[str, Any]]) -> str:
    """Mock 默认响应：区分流式三节点、纠错请求与笔记保存请求。"""
    system = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
    user_contents = [m["content"] for m in messages if m.get("role") == "user"]
    last = user_contents[-1] if user_contents else ""

    if "You are an English coach" in system:
        return _coach_mock_response(last)

    if "TASK: LOCATE_ERRORS" in system:
        return json.dumps(
            {
                "errors": [
                    {
                        "category": "时态错误",
                        "fragment": "go",
                        "span_start": 0,
                        "span_end": 0,
                        "correction": "went",
                        "explanation": "过去时间应用过去式",
                    }
                ]
            },
            ensure_ascii=False,
        )

    if "TASK: MINIMAL_EDIT" in system:
        return json.dumps(
            {"text": "Yesterday I went to school.", "note": "修正时态"},
            ensure_ascii=False,
        )

    if "TASK: NATIVE_FLUENCY" in system:
        return json.dumps(
            {"text": "I went to school yesterday.", "note": "更自然"},
            ensure_ascii=False,
        )

    if "TASK: EXPLAIN_ERROR" in system:
        return json.dumps(
            {
                "text": "go 是过去时间，所以用 went。",
                "turn_id": "t1",
                "error_id": "e1",
            },
            ensure_ascii=False,
        )

    # 笔记保存请求（note_prompt 的 user content 含「## 原文」标记）
    if "## 原文" in last and "## 错误列表" in last:
        return json.dumps(
            {
                "results": [
                    {
                        "rule_title": "介词后加 -ing 形式",
                        "knowledge_point": "介词后接动词时需用动名词形式(-ing)而非不定式。如 be interested in reading、good at swimming。",
                        "alternatives": [
                            "She is interested in reading technical docs.",
                            "He is good at presenting in meetings.",
                            "The team is responsible for shipping the release.",
                        ],
                        "feynman_question": "介词后接动词用什么形式？为什么不能用不定式？",
                        "error_root": "动词形式错误",
                        "cases": [
                            {"change_details": "interested in read → interested in reading"}
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        )

    # 纠错请求
    if "没有错误" in last or "no-error" in last:
        return json.dumps(
            {
                "errors": [],
                "rewrite": {
                    "minimal": {"text": last, "note": "原文已无问题"},
                    "natural": {"text": last, "note": "无需改写"},
                },
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "errors": [
                {
                    "category": "动词形式错误",
                    "fragment": "interested in read",
                    "explanation": "介词后应接动名词形式",
                    "correction": "interested in reading",
                }
            ],
            "rewrite": {
                "minimal": {"text": "I am interested in reading English books.", "note": "介词后接动名词"},
                "natural": {"text": "I love reading English books.", "note": "更自然的表达"},
            },
        },
        ensure_ascii=False,
    )


class MockLLMClient(LLMClient):
    def __init__(self, responder: Callable[[list[dict[str, Any]]], str] | None = None) -> None:
        self.responder = responder or _default_responder
        self.calls: list[list[dict[str, Any]]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool = True,
        json_mode: bool = True,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> str:
        self.calls.append(messages)
        return self.responder(messages)

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        thinking: bool = True,
        json_mode: bool = True,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[dict[str, str]]:
        self.calls.append(messages)
        yield {
            "type": "reasoning",
            "text": "\n".join(
                f"第 {index} 步：检查句子结构、时态、冠词与搭配是否自然。"
                for index in range(1, 31)
            ),
        }
        text = self.responder(messages)
        for start in range(0, len(text), 32):
            yield {"type": "content", "text": text[start : start + 32]}


def _coach_mock_response(last_user: str) -> str:
    """Mock coach：中文提问走 answer，其余走 correct，字段顺序与真实契约一致。"""
    text = last_user.strip()
    question_markers = (
        "?",
        "？",
        "为什么",
        "怎么",
        "如何",
        "什么",
        "吗",
        "呢",
        "why",
        "how",
        "what",
    )
    if any(marker in text.lower() for marker in question_markers):
        return json.dumps(
            {
                "mode": "answer",
                "answer": (
                    "turn on 是英语里“打开（电器/灯）”的固定搭配，"
                    "open 一般只用于门、窗等可物理开合的东西。\n"
                    "例如：Could you turn on the light? 比 Could you open the light? 自然得多。"
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    return json.dumps(
        {
            "mode": "correct",
            "has_errors": True,
            "errors": [
                {
                    "severity": "Major",
                    "fragment": "go",
                    "type": "时态错误",
                    "reason": "yesterday 表示过去，动词应使用过去式",
                    "fix": "went",
                },
                {
                    "severity": "Minor",
                    "fragment": "very big",
                    "type": "中式直译",
                    "reason": "very big 在正式描述中不够自然",
                    "fix": "substantial",
                },
            ],
            "rewrites": {
                "formal": {
                    "text": "Yesterday I went to school and saw a substantial building.",
                    "note": "更正式、更具体的表达",
                },
                "casual": {
                    "text": "I went to school yesterday and saw a really big building.",
                    "note": "口语里 really big 更自然",
                },
                "minimal": {
                    "text": "Yesterday I went to school and saw a very big building."
                },
            },
            "learnings": [
                {
                    "pattern": "过去时间要用过去式",
                    "wrong": "yesterday + 动词原形",
                    "right": "yesterday + 动词过去式",
                    "rule": "句中出现 yesterday 等过去时间状语时，谓语动词需使用过去式。",
                    "examples": ["Yesterday I go to school. ❌ → Yesterday I went to school. ✅"],
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.LLM_MODE == "mock":
        return MockLLMClient()
    if not settings.LLM_BASE_URL or not settings.LLM_API_KEY:
        raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务未配置，请配置 LLM_BASE_URL/LLM_API_KEY")
    return RealLLMClient(
        settings.LLM_BASE_URL,
        settings.LLM_API_KEY,
        settings.LLM_MODEL,
        thinking_param=settings.LLM_THINKING_PARAM,
        thinking_always_on=settings.LLM_THINKING_ALWAYS_ON,
    )
