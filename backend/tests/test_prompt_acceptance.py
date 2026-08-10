import json

from app.scripts.prompt_acceptance import build_messages, run_case, run_acceptance


def _mock_llm(responder):
    async def llm_call(messages, thinking="disabled", base_url=None, api_key=None, model=None):
        return responder(messages, thinking, base_url, api_key, model)
    return llm_call


def test_build_messages_uses_system_prompt():
    msgs = build_messages("Correct the trigger_by field set up logic when creating job.")
    assert msgs[0]["role"] == "system"
    assert "correction" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "Correct the trigger_by field set up logic when creating job."}


async def test_run_case_collects_raw_output():
    raw_json = '{"intent": "correction", "correction": {"has_errors": true}}'
    llm_call = _mock_llm(lambda msgs, thinking, base_url, api_key, model: raw_json)
    case = {"id": "C-01", "input": "hello world", "expect": {}}
    result = await run_case(llm_call, case)
    assert result["id"] == "C-01"
    assert result["input"] == "hello world"
    assert result["output"] == raw_json
    assert result["error"] is None
    assert isinstance(result["elapsed"], (int, float))


async def test_run_case_forwards_thinking():
    seen = {}

    async def llm_call(messages, thinking, base_url=None, api_key=None, model=None):
        seen["thinking"] = thinking
        return '{"intent": "correction", "correction": {"has_errors": false}}'

    case = {"id": "C-01", "input": "hello", "expect": {}}
    await run_case(llm_call, case, thinking="enabled")
    assert seen["thinking"] == "enabled"


async def test_run_case_raises_marks_error():
    async def llm_call(messages, thinking="disabled", base_url=None, api_key=None, model=None):
        raise ConnectionError("boom")

    case = {"id": "X", "input": "hello", "expect": {}}
    result = await run_case(llm_call, case)
    assert result["output"] == ""
    assert result["error"] is not None
    assert "boom" in result["error"]


async def test_run_acceptance_aggregates_raw():
    calls = {"n": 0}

    def responder(messages, thinking, base_url=None, api_key=None, model=None):
        calls["n"] += 1
        return '{"intent": "correction", "correction": {"has_errors": false}}'

    cases = [
        {"id": "A", "input": "a", "expect": {}},
        {"id": "B", "input": "b", "expect": {}},
    ]
    summary = await run_acceptance(_mock_llm(responder), cases)
    assert summary["total"] == 2
    assert calls["n"] == 2
    assert len(summary["results"]) == 2
    assert all(r["error"] is None for r in summary["results"])
    assert summary["prompt"] and "correction" in summary["prompt"]
    assert summary["thinking"] == "disabled"
