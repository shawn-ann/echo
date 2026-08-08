import json
import re
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
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete(self, messages: list[dict[str, Any]]) -> str:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages},
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError from exc


def _default_responder(messages: list[dict[str, Any]]) -> str:
    """Mock 默认响应：中文→追问；含 no-error 标记→无错误报告；其余→纠错报告。"""
    user_contents = [m["content"] for m in messages if m.get("role") == "user"]
    last = user_contents[-1] if user_contents else ""
    if "没有错误" in last or "no-error" in last:
        return json.dumps(
            {"intent": "correction", "correction": {"has_errors": False, "errors": [], "rewrite": None}, "reply": None},
            ensure_ascii=False,
        )
    if re.search(r"[\u4e00-\u9fff]", last):
        return json.dumps(
            {"intent": "follow_up", "reply": "delicious 是极限形容词，通常不加 very。", "correction": None},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "intent": "correction",
            "correction": {
                "has_errors": True,
                "errors": [
                    {
                        "category": "grammar",
                        "fragment": "I go to",
                        "explanation": "yesterday 表示过去，故用过去式 went",
                        "correction": "I went to",
                    }
                ],
                "rewrite": {
                    "minimal": {"text": "Yesterday I went to the park.", "explanation": "修正时态，保留原句结构"},
                    "natural": {"text": "Yesterday I enjoyed the park.", "explanation": "用 enjoyed 更自然"},
                },
            },
            "reply": None,
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
