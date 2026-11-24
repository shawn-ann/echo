import json

import pytest

from app.services.coach_stream import stream_coach_events

CORRECT_REPORT = {
    "mode": "correct",
    "has_errors": True,
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
    "learnings": [
        {
            "pattern": "过去式",
            "wrong": "yesterday + go",
            "right": "yesterday + went",
            "rule": "过去时间用过去式",
            "examples": ["I go yesterday. ❌ → I went yesterday. ✅"],
        }
    ],
}

ANSWER_REPORT = {"mode": "answer", "answer": "第一段\n第二段"}


class FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


class FakeStreamClient:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def complete_stream(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        for chunk in self.chunks:
            yield chunk


def parse_events(raw: str) -> list[tuple[str, dict]]:
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


async def collect(client) -> list[tuple[str, dict]]:
    raw = ""
    async for chunk in stream_coach_events(
        [{"role": "user", "content": "Yesterday I go to school."}],
        FakeRequest(),
        client,
    ):
        raw += chunk
    return parse_events(raw)


def chunks_for(report: dict, size: int = 40) -> list[dict[str, str]]:
    text = json.dumps(report, ensure_ascii=False)
    chunks = [{"type": "reasoning", "text": "先看时态。"}]
    chunks += [
        {"type": "content", "text": text[start : start + size]}
        for start in range(0, len(text), size)
    ]
    return chunks


async def test_stream_emits_incremental_events_and_done_report():
    client = FakeStreamClient(chunks_for(CORRECT_REPORT))
    events = await collect(client)

    names = [name for name, _ in events]
    assert "report_start" in names
    assert names.index("report_start") < names.index("error_added")
    assert "reasoning" in names
    assert "error_added" in names
    assert names.count("rewrite_ready") == 3
    assert "learning_added" in names
    assert names[-1] == "done"

    done = events[-1][1]
    assert done["report"]["mode"] == "correct"
    assert done["report"]["has_errors"] is True
    assert client.calls[0][1]["reasoning_effort"] == "high"


async def test_stream_answer_mode():
    events = await collect(FakeStreamClient(chunks_for(ANSWER_REPORT, size=7)))
    answer = "".join(
        payload["text"] for name, payload in events if name == "answer_delta"
    )
    assert answer == "第一段\n第二段"
    assert events[-1][1]["report"] == ANSWER_REPORT


async def test_stream_invalid_json_falls_back_to_raw():
    client = FakeStreamClient([{"type": "content", "text": '{"mode":"correct"'}])
    events = await collect(client)
    assert events[-1][0] == "done"
    assert events[-1][1]["report"] is None
    assert events[-1][1]["raw"].startswith('{"mode"')


async def test_has_errors_is_normalized_from_errors():
    report = {**CORRECT_REPORT, "has_errors": False}
    events = await collect(FakeStreamClient(chunks_for(report)))
    assert events[-1][1]["report"]["has_errors"] is True


@pytest.mark.parametrize("raw", ["", "not json"])
async def test_stream_handles_empty_output(raw):
    events = await collect(FakeStreamClient([{"type": "content", "text": raw}]))
    assert events[-1][0] == "done"
    assert events[-1][1]["report"] is None
