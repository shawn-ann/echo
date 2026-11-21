import json

import httpx

from app.services.llm_client import (
    LLMTimeoutError,
    LLMUnavailableError,
    MockLLMClient,
    RealLLMClient,
)


async def test_mock_llm_returns_responder_output():
    mock = MockLLMClient(responder=lambda msgs: "pong")
    assert await mock.complete([{"role": "user", "content": "hi"}]) == "pong"


async def test_real_llm_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        # 不再注入 temperature，交给服务端默认值
        assert "temperature" not in body
        assert body["response_format"] == {"type": "json_object"}
        # 思考模式固定开启，不受外部配置影响
        assert body["chat_template_kwargs"] == {"enable_thinking": True}
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    transport = httpx.MockTransport(handler)
    client = RealLLMClient("https://api.example.com", "test-key", "test-model", transport=transport)
    result = await client.complete([{"role": "user", "content": "hi"}])
    assert result == "ok"
    assert calls["n"] == 3


async def test_real_llm_respects_per_call_params():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = RealLLMClient(
        "https://api.example.com", "k", "m", transport=httpx.MockTransport(handler)
    )
    await client.complete(
        [{"role": "user", "content": "hi"}], thinking=False, json_mode=False
    )
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert "response_format" not in captured


async def test_real_llm_all_fail_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    client = RealLLMClient("https://api.example.com", "test-key", "test-model", transport=transport)
    try:
        await client.complete([{"role": "user", "content": "hi"}])
        assert False, "应抛异常"
    except LLMUnavailableError:
        pass


async def test_real_llm_timeout_raises_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow")

    transport = httpx.MockTransport(handler)
    client = RealLLMClient("https://api.example.com", "test-key", "test-model", transport=transport)
    try:
        await client.complete([{"role": "user", "content": "hi"}])
        assert False, "应抛异常"
    except LLMTimeoutError:
        pass
