import json

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import chat
from app.services.chat_stream import stream_chat_events
from app.services.llm_client import get_llm_client
from tests.chat_fakes import ScriptedLLMClient

TEXT = "Yesterday I go to school."
LOCATE_OK = '{"errors":[{"category":"时态错误","fragment":"go","correction":"went","explanation":"过去时间用过去式"}]}'
MINIMAL_OK = '{"text":"Yesterday I went to school.","note":"修正时态"}'
FLUENCY_OK = '{"text":"I went to school yesterday.","note":"更自然"}'


def _app(fake):
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_llm_client] = lambda: fake
    return app


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
    assert names[0] == "errors" and names[-1] == "done"
    assert set(names[1:-1]) == {"minimal", "fluency"}


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
    assert [e for e, _ in _events(r.text)] == ["error", "done"]


async def test_stream_one_rewrite_failure_keeps_other():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=RuntimeError("boom"), fluency=FLUENCY_OK)
    async with AsyncClient(transport=ASGITransport(app=_app(fake)), base_url="http://test") as c:
        r = await c.post("/api/v1/chat/stream", json={"content": TEXT})
    names = [e for e, _ in _events(r.text)]
    assert names[0] == "errors" and names[-1] == "done"
    assert "rewrite_degraded" in names
    assert "fluency" in names
    assert "minimal" not in names


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
    chunks = [c async for c in stream_chat_events(TEXT, fake, Disconnected())]
    assert chunks == []
