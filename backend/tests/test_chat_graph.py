import pytest

from app.graph.build import build_graph
from app.graph.nodes import LocateError
from app.services.llm_client import LLMUnavailableError
from tests.chat_fakes import ScriptedLLMClient

TEXT = "Yesterday I go to school."
LOCATE_OK = '{"errors":[{"category":"时态错误","fragment":"go","correction":"went","explanation":"过去时间用过去式"}]}'


async def test_graph_returns_validated_errors():
    fake = ScriptedLLMClient(locate=LOCATE_OK)
    result = await build_graph(fake).ainvoke({"text": TEXT, "request_id": "t1"})
    assert result["has_errors"] is True
    assert result["errors"] == [
        {"category": "时态错误", "fragment": "go", "correction": "went", "explanation": "过去时间用过去式"}
    ]


async def test_graph_retries_locate_once_then_raises():
    fake = ScriptedLLMClient(locate="not-json")
    with pytest.raises(LocateError):
        await build_graph(fake).ainvoke({"text": TEXT, "request_id": "t2"})
    assert fake.calls == ["locate", "locate"]


MINIMAL_OK = '{"text":"Yesterday I went to school.","note":"修正时态"}'
FLUENCY_OK = '{"text":"I went to school yesterday.","note":"更自然"}'


async def test_graph_runs_both_rewrites():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=MINIMAL_OK, fluency=FLUENCY_OK)
    result = await build_graph(fake).ainvoke({"text": TEXT, "request_id": "t3"})
    assert result["minimal_text"] == "Yesterday I went to school."
    assert result["minimal_note"] == "修正时态"
    assert result["fluency_text"] == "I went to school yesterday."
    assert result["fluency_note"] == "更自然"
    assert set(fake.calls) == {"locate", "minimal", "fluency"}


async def test_graph_no_errors_uses_passthrough_and_still_runs_fluency():
    fake = ScriptedLLMClient(locate='{"errors":[]}', fluency=FLUENCY_OK)
    result = await build_graph(fake).ainvoke({"text": TEXT, "request_id": "t4"})
    assert result["has_errors"] is False
    assert result["minimal_text"] == TEXT
    assert result["minimal_note"] == "原文未发现语法错误，保持原样"
    assert result["fluency_text"] == "I went to school yesterday."
    assert "minimal" not in fake.calls


async def test_graph_minimal_failure_keeps_fluency():
    fake = ScriptedLLMClient(locate=LOCATE_OK, minimal=RuntimeError("boom"), fluency=FLUENCY_OK)
    result = await build_graph(fake).ainvoke({"text": TEXT, "request_id": "t5"})
    assert result["minimal_error"] == "最小修正生成失败"
    assert result["fluency_text"] == "I went to school yesterday."


async def test_graph_message_less_llm_failure_still_marks_error():
    fake = ScriptedLLMClient(
        locate=LOCATE_OK,
        minimal=LLMUnavailableError(),
        fluency=FLUENCY_OK,
    )
    result = await build_graph(fake).ainvoke({"text": TEXT, "request_id": "t6"})
    assert result["minimal_error"] == "最小修正生成失败"
    assert result["fluency_text"] == "I went to school yesterday."
