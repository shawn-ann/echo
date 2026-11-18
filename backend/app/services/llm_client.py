import json
from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


class LLMClient:
    async def complete(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError


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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._transport = transport

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        last_exc: Exception | None = None
        settings = get_settings()
        for _attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120, transport=self._transport) as client:
                    r = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": settings.LLM_TEMPERATURE,
                            "chat_template_kwargs": {"enable_thinking": settings.LLM_ENABLE_THINKING},
                            "response_format": {"type": "json_object"},
                        },
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


def _default_responder(messages: list[dict[str, Any]]) -> str:
    """Mock 默认响应：区分纠错请求与笔记保存请求。"""
    user_contents = [m["content"] for m in messages if m.get("role") == "user"]
    last = user_contents[-1] if user_contents else ""

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
                        "error_root": "动词形式",
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

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        self.calls.append(messages)
        return self.responder(messages)


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.LLM_MODE == "mock":
        return MockLLMClient()
    if not settings.LLM_BASE_URL or not settings.LLM_API_KEY:
        raise AppError(503, "LLM_SERVICE_UNAVAILABLE", "AI 服务未配置，请配置 LLM_BASE_URL/LLM_API_KEY")
    return RealLLMClient(settings.LLM_BASE_URL, settings.LLM_API_KEY, settings.LLM_MODEL)
