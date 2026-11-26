import json

import pytest
from pydantic import ValidationError

from app.schemas.correction_stream import CorrectionStreamRequest
from app.services.correction_stream import build_correction_messages, stream_correction_events

CORRECTION = {
    "errors": [
        {
            "severity": "Major",
            "fragment": "go",
            "type": "时态错误",
            "reason": "过去时间用过去式",
            "fix": "went",
        }
    ],
    "rewrites": {
        "formal": {"text": "Formal.", "note": "正式"},
        "casual": {"text": "Casual.", "note": "口语"},
        "minimal": {"text": "Minimal."},
    },
}


class FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


class FakeClient:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def complete_stream(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        for chunk in self.chunks:
            yield chunk


def parse_events(raw: str):
    events = []
    for frame in raw.strip().split("\n\n"):
        name = ""
        data = ""
        for line in frame.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if name and data:
            events.append((name, json.loads(data)))
    return events


async def collect(client):
    raw = ""
    async for chunk in stream_correction_events(
        "Yesterday I go to school.", FakeRequest(), client
    ):
        raw += chunk
    return parse_events(raw)


def json_chunks(payload, size=32):
    text = json.dumps(payload, ensure_ascii=False)
    return [{"type": "reasoning", "text": "先看时态。"}] + [
        {"type": "content", "text": text[start : start + size]}
        for start in range(0, len(text), size)
    ]


async def test_stream_correction_events():
    client = FakeClient(json_chunks(CORRECTION))
    events = await collect(client)
    names = [name for name, _ in events]

    assert names[0] == "reasoning"
    assert "report_start" in names
    assert names.count("error_added") == 1
    assert names.count("rewrite_ready") == 3
    assert names[-1] == "done"
    assert events[-1][1]["report"]["mode"] == "correct"
    assert events[-1][1]["report"]["has_errors"] is True
    assert "learnings" not in events[-1][1]["report"]
    assert client.calls[0][1]["json_mode"] is True


async def test_invalid_correction_json_falls_back_to_raw():
    events = await collect(FakeClient([{"type": "content", "text": '{"errors":['}]))
    assert events[-1][0] == "done"
    assert events[-1][1]["report"] is None
    assert events[-1][1]["raw"].startswith('{"errors"')


def test_build_messages_uses_coach_prompt_without_history():
    messages = build_correction_messages("She go.")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "English coach" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "She go."}


def test_request_requires_correction_mode():
    assert CorrectionStreamRequest(content="x").mode == "correction"
    with pytest.raises(ValidationError):
        CorrectionStreamRequest(content="x", mode="revision")
