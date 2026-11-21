import pytest

from app.graph.build import build_graph
from app.graph.nodes import LocateError
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
