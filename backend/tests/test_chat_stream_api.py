import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import get_settings
from app.graph.build import build_graph
from app.main import create_app
from app.routers import chat
from app.services.chat_stream import stream_chat_events
from app.services.llm_client import LLMUnavailableError
from tests.chat_fakes import ScriptedLLMClient

TEXT = "Yesterday I go to school."
LOCATE_OK = '{"errors":[{"category":"时态错误","fragment":"go","correction":"went","explanation":"过去时间用过去式"}]}'
MINIMAL_OK = '{"text":"Yesterday I went to school.","note":"修正时态"}'
FLUENCY_OK = '{"text":"I went to school yesterday.","note":"更自然"}'
EXPLAIN_OK = '{"text":"go 是过去时间，所以用 went。","turn_id":"t1","error_id":"e1"}'


def _app(fake):
    app = FastAPI()
    app.include_router(chat.router)
    app.state.chat_graph = build_graph(fake, MemorySaver())
    return app


def test_get_chat_graph_builds_once_under_concurrency(monkeypatch):
    calls: list[int] = []
    fake_graph = object()

    def fake_build(*args, **kwargs):
        time.sleep(0.02)
        calls.append(1)
        return fake_graph

    monkeypatch.setattr(chat, "build_graph", fake_build)
    monkeypatch.setattr(chat, "get_llm_client", lambda: object())
    app = SimpleNamespace(state=SimpleNamespace())
    request = SimpleNamespace(app=app)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: chat.get_chat_graph(request), range(2)))

    assert len(calls) == 1
    assert results[0] is results[1] is fake_graph


def test_chat_stream_router_disabled_by_setting(monkeypatch):
    monkeypatch.setenv("STREAM_MVP_ENABLED", "false")
    get_settings.cache_clear()
    try:
        app = create_app()
        assert "/api/v1/chat/stream" not in app.openapi()["paths"]
    finally:
        get_settings.cache_clear()


def test_chat_stream_router_enabled_with_setting(monkeypatch):
    monkeypatch.setenv("STREAM_MVP_ENABLED", "true")
    get_settings.cache_clear()
    try:
        app = create_app()
        assert "/api/v1/chat/stream" in app.openapi()["paths"]
    finally:
        get_settings.cache_clear()


def _events(body: str) -> list[tuple[str, dict]]:
    result = []
    for frame in body.strip().split("\n\n"):
        event = next(line[7:] for line in frame.splitlines() if line.startswith("event: "))
        data = next(line[6:] for line in frame.splitlines() if line.startswith("data: "))
        result.append((event, json.loads(data)))
    return result


async def test_stream_normal_events():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK)
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    assert r.status_code == 200
    events = _events(r.text)
    names = [e for e, _ in events]
    assert names[:3] == ["thread", "intent", "errors"]
    assert names[-1] == "done"
    assert set(names[3:-1]) == {"minimal", "fluency"}


async def test_stream_no_errors_still_returns_fluency():
    fake = ScriptedLLMClient(locate='{"errors":[]}', fluency=FLUENCY_OK)
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    events = dict(_events(r.text))
    assert events["errors"]["has_errors"] is False
    assert events["minimal"]["text"] == TEXT
    assert events["fluency"]["text"] == "I went to school yesterday."


async def test_stream_locate_failure_is_terminal_error():
    fake = ScriptedLLMClient(locate="not-json")
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    assert [e for e, _ in _events(r.text)] == ["thread", "intent", "error", "done"]


async def test_stream_one_rewrite_failure_keeps_other():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=RuntimeError("boom"), fluency=FLUENCY_OK)
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    names = [e for e, _ in _events(r.text)]
    assert names[0] == "thread" and names[1] == "intent" and names[-1] == "done"
    assert "rewrite_degraded" in names
    assert "fluency" in names
    assert "minimal" not in names


async def test_stream_message_less_llm_failure_is_degraded():
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        minimal=LLMUnavailableError(),
        fluency=FLUENCY_OK,
    )
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    events = _events(r.text)
    degraded = [payload for name, payload in events if name == "rewrite_degraded"]
    assert degraded == [{"stage": "minimal", "message": "最小修正生成失败"}]
    assert "minimal" not in [name for name, _ in events]


async def test_stream_rejects_empty_content():
    fake = ScriptedLLMClient(locate=LOCATE_OK)
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": ""})
    assert r.status_code in (400, 422)


async def test_stream_stops_when_client_disconnected():
    class Disconnected:
        async def is_disconnected(self):
            return True

    fake = ScriptedLLMClient(locate=LOCATE_OK)
    graph = build_graph(fake, MemorySaver())
    chunks = [
        c
        async for c in stream_chat_events(
            TEXT, graph, Disconnected(), thread_id="t1"
        )
    ]
    assert chunks == []


async def test_stream_emits_thread_and_intent():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    app = _app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    names = [e for e, _ in _events(r.text)]
    assert names[0] == "thread"
    assert names[1] == "intent"
    assert names[-1] == "done"


async def test_stream_followup_uses_same_thread():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    app = _app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        first = await c.post("/api/v1/chat/stream", json={"content": TEXT})
        thread_id = next(payload["thread_id"] for e, payload in _events(first.text) if e == "thread")
        fake.calls.clear()
        second = await c.post(
            "/api/v1/chat/stream",
            json={
                "content": "为什么 go 改成 went？",
                "thread_id": thread_id,
                "turn_id": "t1",
                "error_id": "e1",
            },
        )
    events = _events(second.text)
    names = [e for e, _ in events]
    assert names == ["thread", "intent", "explanation", "done"]
    assert events[1][1]["intent"] == "followup"
    assert fake.calls == ["explain"]
