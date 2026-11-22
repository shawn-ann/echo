from app.services.chat_stream import events_from_update, format_sse


def test_validate_update_maps_to_errors():
    update = {"current_turn_id": "t1", "has_errors": True, "errors": [{"category": "时态错误"}]}
    assert events_from_update("validate_errors", update) == [
        ("errors", {"turn_id": "t1", "has_errors": True, "errors": [{"category": "时态错误"}]})
    ]


def test_route_update_maps_to_intent():
    assert events_from_update("route", {"intent": "followup"}) == [
        ("intent", {"intent": "followup"})
    ]


def test_explain_update_maps_to_explanation():
    assert events_from_update(
        "explain",
        {"explanation": "因为...", "explanation_turn_id": "t2", "explanation_error_id": "e3"},
    ) == [
        ("explanation", {"text": "因为...", "turn_id": "t2", "error_id": "e3"})
    ]


def test_explain_error_maps_to_error():
    assert events_from_update("explain", {"explanation_error": "没有可追问的错误"}) == [
        ("error", {"code": "EXPLAIN_FAILED", "message": "没有可追问的错误"})
    ]


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


def test_empty_error_string_still_maps_to_degraded():
    assert events_from_update("minimal_edit", {"minimal_error": ""}) == [
        ("rewrite_degraded", {"stage": "minimal", "message": "改写生成失败"})
    ]


def test_unknown_node_emits_nothing():
    assert events_from_update("error_locate", {"raw_errors": []}) == []


def test_format_sse_keeps_unicode_and_blank_line():
    assert format_sse("errors", {"note": "中文"}) == 'event: errors\ndata: {"note": "中文"}\n\n'
