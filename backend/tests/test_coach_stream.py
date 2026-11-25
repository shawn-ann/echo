import json

from app.services.coach_stream import (
    extract_json_object,
    stream_coach_events,
    strip_code_fence,
    validate_correction,
)

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


def chunks_for_json(payload: dict, size: int = 40) -> list[dict[str, str]]:
    text = json.dumps(payload, ensure_ascii=False)
    chunks = [{"type": "reasoning", "text": "先看时态。"}]
    chunks += [
        {"type": "content", "text": text[start : start + size]}
        for start in range(0, len(text), size)
    ]
    return chunks


async def test_correction_json_events_and_done_report():
    client = FakeStreamClient(chunks_for_json(CORRECTION))
    events = await collect(client)

    names = [name for name, _ in events]
    assert names[0] == "reasoning"
    assert names[1] == "report_start"
    assert names.count("error_added") == 1
    assert names.count("rewrite_ready") == 3
    assert names[-1] == "done"

    done = events[-1][1]
    assert done["report"]["mode"] == "correct"
    assert done["report"]["has_errors"] is True
    assert done["report"]["errors"][0]["fix"] == "went"
    assert "learnings" not in done["report"]
    assert client.calls[0][1]["json_mode"] is False


async def test_plain_text_answer_streams_without_json():
    chunks = [
        {"type": "reasoning", "text": "这是用法问题。"},
        {"type": "content", "text": "turn on 是固定搭配，"},
        {"type": "content", "text": "open 只用于可物理开合的东西。"},
    ]
    events = await collect(FakeStreamClient(chunks))
    names = [name for name, _ in events]

    assert names[0] == "reasoning"
    assert names[1] == "report_start"
    assert events[1][1]["mode"] == "answer"
    assert names.count("answer_delta") == 2
    answer = "".join(p["text"] for n, p in events if n == "answer_delta")
    assert answer.startswith("turn on")
    assert events[-1][1]["report"] == {
        "mode": "answer",
        "answer": "turn on 是固定搭配，open 只用于可物理开合的东西。",
    }


async def test_text_starting_with_brace_is_not_mistaken_for_answer():
    payload = {"errors": [], "rewrites": CORRECTION["rewrites"]}
    client = FakeStreamClient(
        [{"type": "content", "text": json.dumps(payload, ensure_ascii=False)}]
    )
    events = await collect(client)
    assert next(p for n, p in events if n == "report_start")["mode"] == "correct"
    assert events[-1][1]["report"]["mode"] == "correct"


async def test_invalid_json_falls_back_to_raw():
    client = FakeStreamClient([{"type": "content", "text": '{"errors":['}])
    events = await collect(client)
    assert next(p for n, p in events if n == "report_start")["mode"] == "correct"
    assert events[-1][0] == "done"
    assert events[-1][1]["report"] is None
    assert events[-1][1]["raw"].startswith('{"errors"')


async def test_empty_output_returns_empty_raw():
    events = await collect(FakeStreamClient([{"type": "content", "text": "   "}]))
    assert events[-1] == ("done", {"report": None, "raw": ""})


def test_strip_code_fence():
    raw = '```json\n{"errors": [], "rewrites": {}}\n```'
    assert strip_code_fence(raw) == '{"errors": [], "rewrites": {}}'


async def test_fenced_json_is_parsed():
    raw = '```json\n' + json.dumps(CORRECTION, ensure_ascii=False) + "\n```"
    events = await collect(FakeStreamClient([{"type": "content", "text": raw}]))
    assert next(p for n, p in events if n == "report_start")["mode"] == "correct"
    assert events[-1][1]["report"]["mode"] == "correct"


def test_validate_correction_derives_nothing_about_learnings():
    correction = validate_correction(json.dumps(CORRECTION))
    assert correction is not None
    assert len(correction.errors) == 1


def test_extract_json_object_ignores_trailing_text():
    raw = json.dumps(CORRECTION, ensure_ascii=False) + "\n\nHope this helps."
    extracted = extract_json_object(raw)
    assert extracted.startswith("{")
    assert extracted.endswith("}")
    correction = validate_correction(raw)
    assert correction is not None
