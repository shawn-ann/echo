import pytest

from app.graph.build import build_graph
from app.graph.nodes import (
    LocateError,
    make_explain_node,
    resolve_target_node,
    route_node,
)
from app.services.llm_client import LLMUnavailableError
from tests.chat_fakes import ScriptedLLMClient

TEXT = "Yesterday I go to school."
LOCATE_OK = '{"errors":[{"category":"时态错误","fragment":"go","correction":"went","explanation":"过去时间用过去式"}]}'


async def test_graph_returns_validated_errors():
    fake = ScriptedLLMClient(locate=LOCATE_OK)
    result = await build_graph(fake).ainvoke({"content": TEXT, "request_id": "t1"})
    start = TEXT.index("go")
    assert result["has_errors"] is True
    assert result["errors"] == [
        {
            "error_id": "e1",
            "category": "时态错误",
            "fragment": "go",
            "correction": "went",
            "explanation": "过去时间用过去式",
            "span_start": start,
            "span_end": start + 2,
        }
    ]


async def test_graph_retries_locate_once_then_raises():
    fake = ScriptedLLMClient(locate="not-json")
    with pytest.raises(LocateError):
        await build_graph(fake).ainvoke({"content": TEXT, "request_id": "t2"})
    assert fake.calls == ["locate", "locate"]


MINIMAL_OK = '{"text":"Yesterday I went to school.","note":"修正时态"}'
FLUENCY_OK = '{"text":"I went to school yesterday.","note":"更自然"}'


async def test_graph_runs_both_rewrites():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK)
    result = await build_graph(fake).ainvoke({"content": TEXT, "request_id": "t3"})
    assert result["minimal_text"] == "Yesterday I went to school."
    assert result["minimal_note"] == "修正时态"
    assert result["fluency_text"] == "I went to school yesterday."
    assert result["fluency_note"] == "更自然"
    assert set(fake.calls) == {"locate", "minimal", "fluency"}
    params = {
        name: (effort, temp)
        for name, effort, temp in zip(
            fake.calls, fake.reasoning_efforts, fake.temperatures
        )
    }
    assert params == {
        "locate": ("high", 0.1),
        "minimal": ("low", 0.1),
        "fluency": ("low", 0.3),
    }


async def test_graph_no_errors_uses_passthrough_and_still_runs_fluency():
    fake = ScriptedLLMClient(locate='{"errors":[]}', fluency=FLUENCY_OK)
    result = await build_graph(fake).ainvoke({"content": TEXT, "request_id": "t4"})
    assert result["has_errors"] is False
    assert result["minimal_text"] == TEXT
    assert result["minimal_note"] == "原文未发现语法错误，保持原样"
    assert result["fluency_text"] == "I went to school yesterday."
    assert "minimal" not in fake.calls


async def test_graph_minimal_failure_keeps_fluency():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=RuntimeError("boom"), fluency=FLUENCY_OK)
    result = await build_graph(fake).ainvoke({"content": TEXT, "request_id": "t5"})
    assert result["minimal_error"] == "最小修正生成失败"
    assert result["fluency_text"] == "I went to school yesterday."


async def test_graph_message_less_llm_failure_still_marks_error():
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        minimal=LLMUnavailableError(),
        fluency=FLUENCY_OK,
    )
    result = await build_graph(fake).ainvoke({"content": TEXT, "request_id": "t6"})
    assert result["minimal_error"] == "最小修正生成失败"
    assert result["fluency_text"] == "I went to school yesterday."


def test_route_explicit_followup():
    state = {"content": "为什么", "hint_intent": "followup", "errors": [{"error_id": "e1"}]}
    assert route_node(state)["intent"] == "followup"


def test_route_no_errors_is_correct():
    assert route_node({"content": "I go to school."})["intent"] == "correct"


def test_route_question_with_errors_is_followup():
    state = {"content": "第二个为什么这么改？", "errors": [{"error_id": "e1"}, {"error_id": "e2"}]}
    assert route_node(state)["intent"] == "followup"


def test_route_english_sentence_with_errors_is_correct():
    state = {"content": "She go to school.", "errors": [{"error_id": "e1"}]}
    assert route_node(state)["intent"] == "correct"


def test_route_cjk_question_with_prior_turn_is_followup():
    state = {
        "content": "为社么用what，不用how",
        "turns": [{"turn_id": "t1", "text": "What is the weather today?", "errors": []}],
        "turn_seq": 1,
    }
    assert route_node(state)["intent"] == "followup"


def test_route_english_with_chinese_placeholder_is_correct():
    state = {
        "content": "I don't like 辣椒。 - 有些词不会写",
        "turns": [{"turn_id": "t1", "text": "What is the weather today?", "errors": []}],
        "turn_seq": 1,
    }
    assert route_node(state)["intent"] == "correct"


def test_route_english_question_with_chinese_note_is_correct():
    state = {
        "content": "What is the weather today? - 不会写 weather",
        "turns": [{"turn_id": "t1", "text": "Hello.", "errors": []}],
        "turn_seq": 1,
    }
    assert route_node(state)["intent"] == "correct"


def test_route_chinese_followup_marker_after_english_start_is_followup():
    state = {
        "content": "what 为什么不用 how？",
        "turns": [{"turn_id": "t1", "text": "What is the weather today?", "errors": []}],
        "turn_seq": 1,
    }
    assert route_node(state)["intent"] == "followup"


def test_route_error_id_forces_followup():
    state = {"content": "解释一下", "error_id": "e2", "errors": [{"error_id": "e1"}]}
    assert route_node(state)["intent"] == "followup"


TURNS = [{
    "turn_id": "t1",
    "text": TEXT,
    "errors": [{"error_id": "e1", "category": "时态错误", "fragment": "go",
                "correction": "went", "explanation": "x", "span_start": 12, "span_end": 14}],
}]


def test_resolve_target_direct_by_explicit_ref():
    assert resolve_target_node({
        "turns": TURNS, "turn_id": "t1", "error_id": "e1", "content": "解释",
    }) == {
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "resolved_variant": None,
        "candidate_refs": [],
        "target_error": None,
    }


def test_resolve_target_free_text_does_not_guess():
    result = resolve_target_node({
        "turns": TURNS, "content": "为什么 go 改成 went？",
    })
    assert result["resolution_status"] == "fuzzy"
    assert result["resolved_turn_id"] is None
    assert result["resolved_error_id"] is None
    assert result["target_error"] is None


def test_resolve_target_free_text_rewrite_question_is_fuzzy():
    result = resolve_target_node({
        "turns": REWRITE_TURNS, "content": "为什么省略would 什么时候简写？",
    })
    assert result["resolution_status"] == "fuzzy"
    assert result["resolved_turn_id"] is None


def test_resolve_target_explicit_turn_scope():
    result = resolve_target_node({
        "turns": TURNS, "turn_id": "t1", "content": "这里为什么这么改？",
    })
    assert result["resolution_status"] == "turn"
    assert result["resolved_turn_id"] == "t1"
    assert result["resolved_error_id"] is None


def test_resolve_target_explicit_variant_uses_latest_turn():
    result = resolve_target_node({
        "turns": REWRITE_TURNS, "rewrite_variant": "both", "content": "这两版区别？",
    })
    assert result["resolution_status"] == "rewrite"
    assert result["resolved_turn_id"] == "t1"
    assert result["resolved_variant"] == "both"
    assert result["resolved_error_id"] is None


def test_resolve_target_explicit_variant_with_explicit_turn():
    turns = REWRITE_TURNS + [{
        "turn_id": "t2", "text": "He go.", "errors": [],
        "minimal_text": "He goes.", "fluency_text": "He goes.",
    }]
    result = resolve_target_node({
        "turns": turns, "turn_id": "t1", "rewrite_variant": "minimal",
    })
    assert result["resolution_status"] == "rewrite"
    assert result["resolved_turn_id"] == "t1"
    assert result["resolved_variant"] == "minimal"


def test_resolve_target_unknown_variant_falls_back_to_fuzzy():
    result = resolve_target_node({
        "turns": TURNS, "rewrite_variant": "fancy", "content": "解释",
    })
    assert result["resolution_status"] == "fuzzy"
    assert result["resolved_variant"] is None


def test_resolve_target_explicit_error_scans_all_turns():
    turns = [
        {"turn_id": "t1", "text": TEXT, "errors": [{"error_id": "e1", "fragment": "go"}]},
        {"turn_id": "t2", "text": "She go.", "errors": [{"error_id": "e1", "fragment": "go"}]},
    ]
    result = resolve_target_node({"turns": turns, "error_id": "e2"})
    assert result["resolution_status"] == "none"
    assert result["target_error"]


REWRITE_TURNS = [{
    "turn_id": "t1",
    "text": "I would like to know how is the wheather tomorrow? Then can I know what coat to dress.",
    "errors": [{
        "error_id": "e1", "category": "词序不当",
        "fragment": "how is the wheather", "correction": "how the wheather is",
        "explanation": "x", "span_start": 21, "span_end": 40,
    }],
    "minimal_text": "I would like to know how the wheather is tomorrow? Then I can know what coat to wear.",
    "minimal_note": "x",
    "fluency_text": "I'd like to know what the weather will be like tomorrow so I can decide which coat to wear.",
    "fluency_note": "x",
}]


def test_resolve_target_explicit_missing_sets_target_error():
    result = resolve_target_node({"turns": TURNS, "turn_id": "t1", "error_id": "e9"})
    assert result["resolution_status"] == "none"
    assert result["target_error"]


def test_resolve_target_trimmed_history_returns_range_error():
    turns = [{
        "turn_id": "t2",
        "text": TEXT,
        "errors": [{"error_id": "e1", "fragment": "go", "correction": "went"}],
    }]
    result = resolve_target_node({
        "turns": turns, "turn_id": "t1", "error_id": "e1", "turn_seq": 11,
    })
    assert result["target_error"] == "历史已超出范围"


EXPLAIN_OK = '{"text": "go 是过去时间，所以用 went。", "turn_id": "t1", "error_id": "e1"}'


async def test_explain_uses_selected_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain=EXPLAIN_OK)
    node = make_explain_node(fake)
    result = await node({
        "turns": TURNS,
        "question": "为什么？",
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
    })
    assert result["explanation"] == "go 是过去时间，所以用 went。"
    assert result["explanation_turn_id"] == "t1"
    assert result["explanation_error_id"] == "e1"


async def test_explain_free_text_uses_model_turn_and_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain=EXPLAIN_OK)
    result = await make_explain_node(fake)({
        "turns": TURNS,
        "question": "为什么 go 改成 went？",
        "resolution_status": "fuzzy",
        "resolved_turn_id": None,
        "resolved_error_id": None,
        "candidate_refs": [],
    })
    assert result["explanation_error_id"] == "e1"
    assert result["explanation_focus"]["kind"] == "error"


EXPLAIN_TURN_LEVEL = '{"text": "would like → \'d like 是口语缩写。", "turn_id": "t1", "error_id": null, "focus": {"kind": "rewrite", "variant": "both"}}'


async def test_explain_free_text_rewrite_answer_is_accepted():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain=EXPLAIN_TURN_LEVEL)
    result = await make_explain_node(fake)({
        "turns": REWRITE_TURNS,
        "question": "为什么省略would 什么时候简写？",
        "resolution_status": "fuzzy",
        "resolved_turn_id": None,
        "resolved_error_id": None,
        "candidate_refs": [],
    })
    assert result["explanation"] == "would like → 'd like 是口语缩写。"
    assert result["explanation_error"] is None
    assert result["explanation_turn_id"] == "t1"
    assert result["explanation_error_id"] is None


async def test_explain_turn_scope_degrades_unknown_error_id():
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        explain='{"text": "x", "turn_id": "t1", "error_id": "e9"}',
    )
    result = await make_explain_node(fake)({
        "turns": REWRITE_TURNS,
        "question": "为什么省略would？",
        "resolution_status": "turn",
        "resolved_turn_id": "t1",
        "resolved_error_id": None,
        "candidate_refs": [],
    })
    assert result["explanation"] == "x"
    assert result["explanation_error"] is None
    assert result["explanation_error_id"] is None


async def test_explain_free_text_unknown_turn_falls_back_to_latest():
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        explain='{"text": "上一句的说明。", "turn_id": "t9", "error_id": null}',
    )
    result = await make_explain_node(fake)({
        "turns": TURNS,
        "question": "刚才那句呢？",
        "resolution_status": "fuzzy",
        "resolved_turn_id": None,
        "resolved_error_id": None,
        "candidate_refs": [],
    })
    assert result["explanation"] == "上一句的说明。"
    assert result["explanation_turn_id"] == "t1"


async def test_explain_explicit_variant_keeps_scope():
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        explain='{"text": "两版区别在于语域。", "turn_id": "t1", "error_id": null}',
    )
    result = await make_explain_node(fake)({
        "turns": REWRITE_TURNS,
        "question": "这两版有什么区别？",
        "resolution_status": "rewrite",
        "resolved_turn_id": "t1",
        "resolved_error_id": None,
        "resolved_variant": "both",
        "candidate_refs": [],
    })
    assert result["explanation_focus"] == {
        "kind": "rewrite",
        "turn_id": "t1",
        "error_id": None,
        "variant": "both",
    }


async def test_explain_without_history_returns_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK)
    result = await make_explain_node(fake)({"turns": [], "question": "为什么"})
    assert result["explanation_error"]


async def test_explain_invalid_resolved_ids_returns_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain='{"text": "x", "turn_id": "t9", "error_id": "e9"}')
    result = await make_explain_node(fake)({
        "turns": TURNS,
        "question": "为什么",
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
    })
    assert result["explanation_error"]


async def test_explain_honors_target_error():
    fake = ScriptedLLMClient(locate=LOCATE_OK, explain=EXPLAIN_OK)
    result = await make_explain_node(fake)({
        "turns": TURNS,
        "question": "为什么",
        "target_error": "找不到指定的错误条目",
    })
    assert result["explanation_error"] == "找不到指定的错误条目"


async def test_explain_direct_rejects_model_switch():
    turns = TURNS + [{
        "turn_id": "t2",
        "text": TEXT,
        "errors": [{"error_id": "e1", "fragment": "go", "correction": "goes"}],
    }]
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        explain='{"text": "x", "turn_id": "t2", "error_id": "e1"}',
    )
    result = await make_explain_node(fake)({
        "turns": turns,
        "question": "为什么",
        "resolution_status": "direct",
        "resolved_turn_id": "t1",
        "resolved_error_id": "e1",
        "candidate_refs": [],
    })
    assert result["explanation_error"]


from langgraph.checkpoint.memory import MemorySaver


async def test_followup_reuses_errors_without_locate():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    await graph.ainvoke({"content": TEXT}, config=config)
    fake.calls.clear()
    result = await graph.ainvoke({"content": "为什么 go 改成 went？"}, config=config)
    assert result["intent"] == "followup"
    assert result["explanation"] == "go 是过去时间，所以用 went。"
    assert result["explanation_turn_id"] == "t1"
    assert result["explanation_error_id"] == "e1"
    assert result["turns"]
    assert "locate" not in fake.calls


async def test_new_correction_clears_old_errors():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t2"}}
    await graph.ainvoke({"content": TEXT}, config=config)
    fake.locate = '{"errors":[{"category":"主谓不一致","fragment":"She go","correction":"She goes","explanation":"第三人称单数","span_start":0,"span_end":6}]}'
    result = await graph.ainvoke({"content": "She go home."}, config=config)
    assert result["intent"] == "correct"
    assert result["errors"][0]["fragment"] == "She go"
    assert result["errors"][0]["error_id"] == "e1"
    assert result["explanation"] in (None, "")


async def test_empty_error_correction_keeps_turn_with_rewrites():
    fake = ScriptedLLMClient(locate='{"errors":[]}', fluency=FLUENCY_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t-empty"}}
    await graph.ainvoke({"content": TEXT}, config=config)
    state = await graph.aget_state(config)
    assert len(state.values["turns"]) == 1
    assert state.values["turns"][0]["errors"] == []
    assert state.values["turns"][0]["fluency_text"] == "I went to school yesterday."
    assert state.values["turn_seq"] == 1


async def test_followup_after_no_error_uses_rewrites_without_locate():
    fake = ScriptedLLMClient(
        locate='{"errors":[]}',
        fluency=FLUENCY_OK,
        explain='{"text": "原句语法正确，地道改写更自然。", "turn_id": "t1", "error_id": null}',
    )
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t-noerr"}}
    await graph.ainvoke({"content": "What is the weather today?"}, config=config)
    fake.calls.clear()
    result = await graph.ainvoke(
        {"content": "为社么用what，不用how"}, config=config
    )
    assert result["intent"] == "followup"
    assert result["explanation"] == "原句语法正确，地道改写更自然。"
    assert "locate" not in fake.calls


async def test_history_keeps_last_ten_turns():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    config = {"configurable": {"thread_id": "t3"}}
    for _ in range(11):
        await graph.ainvoke({"content": TEXT}, config=config)
    state = await graph.aget_state(config)
    assert len(state.values["turns"]) == 10
    assert state.values["turns"][0]["turn_id"] == "t2"
    assert state.values["turns"][-1]["turn_id"] == "t11"


async def test_threads_are_isolated():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK, explain=EXPLAIN_OK)
    graph = build_graph(fake, MemorySaver())
    await graph.ainvoke({"content": TEXT}, config={"configurable": {"thread_id": "a"}})
    result = await graph.ainvoke(
        {"content": "为什么？", "error_id": "e1"}, config={"configurable": {"thread_id": "b"}}
    )
    assert result["intent"] == "followup"
    assert result["explanation_error"]
