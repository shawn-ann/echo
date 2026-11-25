import json

from app.services.coach_events import CoachEventMapper
from app.services.partial_json import parse_partial

REPORT = {
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
}


def names(events):
    return [name for name, _ in events]


def feed_in_pieces(mapper, raw, size=17):
    collected = []
    for end in range(size, len(raw) + size, size):
        collected += mapper.feed(parse_partial(raw[:end]))
    return collected


def test_force_mode_is_idempotent():
    mapper = CoachEventMapper()
    assert names(mapper.force_mode("correct")) == ["report_start"]
    assert mapper.force_mode("correct") == []


def test_events_are_emitted_as_sections_close():
    raw = json.dumps(REPORT, ensure_ascii=False)
    mapper = CoachEventMapper()
    start = mapper.force_mode("correct")
    events = start + feed_in_pieces(mapper, raw)

    assert names(events) == [
        "report_start",
        "error_added",
        "error_added",
        "rewrite_ready",
        "rewrite_ready",
        "rewrite_ready",
    ]
    errors = [p for n, p in events if n == "error_added"]
    assert [e["index"] for e in errors] == [0, 1]
    assert errors[0]["severity"] == "Major"
    assert {p["variant"] for n, p in events if n == "rewrite_ready"} == {
        "formal",
        "casual",
        "minimal",
    }


def test_feed_is_idempotent():
    raw = json.dumps(REPORT, ensure_ascii=False)
    mapper = CoachEventMapper()
    mapper.force_mode("correct")
    feed_in_pieces(mapper, raw)
    assert mapper.feed(parse_partial(raw)) == []


def test_feed_without_mode_emits_nothing():
    raw = json.dumps(REPORT, ensure_ascii=False)
    mapper = CoachEventMapper()
    assert mapper.feed(parse_partial(raw)) == []


def test_feed_report_fills_missing_items():
    mapper = CoachEventMapper()
    mapper.force_mode("correct")
    events = mapper.feed_report(REPORT)
    assert names(events) == [
        "error_added",
        "error_added",
        "rewrite_ready",
        "rewrite_ready",
        "rewrite_ready",
    ]
