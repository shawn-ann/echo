import json

from app.services.coach_events import CoachEventMapper
from app.services.partial_json import parse_partial

REPORT = {
    "mode": "correct",
    "has_errors": True,
    "errors": [
        {
            "severity": "Major",
            "fragment": "go",
            "type": "时态错误",
            "reason": "过去时间用过去式",
            "fix": "went",
        },
        {
            "severity": "Minor",
            "fragment": "very big",
            "type": "中式直译",
            "reason": "不够自然",
            "fix": "substantial",
        },
    ],
    "rewrites": {
        "formal": {"text": "Formal version.", "note": "正式"},
        "casual": {"text": "Casual version.", "note": "口语"},
        "minimal": {"text": "Minimal version."},
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

ANSWER = {"mode": "answer", "answer": "第一段\n第二段"}


def names(events):
    return [name for name, _ in events]


def feed_in_pieces(mapper, raw, size=17):
    collected = []
    for end in range(size, len(raw) + size, size):
        partial = parse_partial(raw[:end])
        collected += mapper.feed(partial)
    return collected


def test_events_are_emitted_as_sections_close():
    raw = json.dumps(REPORT, ensure_ascii=False)
    mapper = CoachEventMapper()
    events = feed_in_pieces(mapper, raw)

    assert names(events)[0] == "report_start"
    assert [e for e in names(events) if e == "error_added"] == ["error_added", "error_added"]
    assert {p["variant"] for n, p in events if n == "rewrite_ready"} == {
        "formal",
        "casual",
        "minimal",
    }
    assert [e for e in names(events) if e == "learning_added"] == ["learning_added"]

    first = next(p for n, p in events if n == "report_start")
    assert first == {"schema_version": 1, "mode": "correct"}
    errors = [p for n, p in events if n == "error_added"]
    assert [e["index"] for e in errors] == [0, 1]
    assert errors[0]["severity"] == "Major"


def test_feed_is_idempotent():
    raw = json.dumps(REPORT, ensure_ascii=False)
    mapper = CoachEventMapper()
    feed_in_pieces(mapper, raw)
    again = mapper.feed(parse_partial(raw))
    assert again == []


def test_feed_report_fills_missing_items():
    mapper = CoachEventMapper()
    mapper.feed(parse_partial('{"mode":"correct"}'))
    events = mapper.feed_report(REPORT)
    assert names(events) == [
        "error_added",
        "error_added",
        "rewrite_ready",
        "rewrite_ready",
        "rewrite_ready",
        "learning_added",
    ]


def test_answer_mode_streams_suffix_only():
    raw = json.dumps(ANSWER, ensure_ascii=False)
    mapper = CoachEventMapper()
    events = feed_in_pieces(mapper, raw, size=5)
    assert names(events)[0] == "report_start"
    assert next(p for n, p in events if n == "report_start")["mode"] == "answer"
    merged = "".join(p["text"] for n, p in events if n == "answer_delta")
    assert merged == "第一段\n第二段"


def test_mode_arriving_late_does_not_emit_partial_events():
    mapper = CoachEventMapper()
    assert mapper.feed(parse_partial('{"answer":"hi"}')) == []
    events = mapper.feed(parse_partial('{"mode":"answer","answer":"hi"}'))
    assert names(events) == ["report_start", "answer_delta"]
