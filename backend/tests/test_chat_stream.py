from app.services.chat_stream import events_from_update, format_sse


def test_validate_update_maps_to_errors():
    update = {"has_errors": True, "errors": [{"category": "时态错误"}]}
    assert events_from_update("validate_errors", update) == [("errors", update)]


def test_minimal_update_maps_to_minimal():
    update = {"minimal_text": "I went.", "minimal_note": "修正时态"}
    assert events_from_update("minimal_edit", update) == [
        ("minimal", {"text": "I went.", "note": "修正时态"})
    ]
    assert events_from_update("minimal_passthrough", update) == [
        ("minimal", {"text": "I went.", "note": "修正时态"})
    ]


def test_rewrite_failure_maps_to_degraded():
    assert events_from_update("minimal_edit", {"minimal_error": "boom"}) == [
        ("rewrite_degraded", {"stage": "minimal", "message": "boom"})
    ]
    assert events_from_update("native_fluency", {"fluency_error": "boom"}) == [
        ("rewrite_degraded", {"stage": "fluency", "message": "boom"})
    ]


def test_unknown_node_emits_nothing():
    assert events_from_update("error_locate", {"raw_errors": []}) == []


def test_format_sse_keeps_unicode_and_blank_line():
    assert format_sse("errors", {"note": "中文"}) == 'event: errors\ndata: {"note": "中文"}\n\n'
