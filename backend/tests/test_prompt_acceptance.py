import json

from app.scripts.prompt_acceptance import build_messages, run_case, run_acceptance


def _mock_llm(responder):
    async def llm_call(messages):
        return responder(messages)
    return llm_call


def test_build_messages_uses_system_prompt():
    msgs = build_messages("Correct the trigger_by field set up logic when creating job.")
    assert msgs[0]["role"] == "system"
    assert "correction" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "Correct the trigger_by field set up logic when creating job."}


async def test_run_case_success():
    report = {
        "intent": "correction",
        "correction": {
            "has_errors": True,
            "errors": [
                {"category": "grammar", "error_type": "冠词缺失", "fragment": "creating job",
                 "explanation": "x", "correction": "creating a job"}
            ],
            "rewrite": {
                "minimal": {"text": "Correct the trigger_by field setup logic when creating a job.", "explanation": "仅修正"},
                "natural": {"text": "Fix the trigger_by field setup logic when creating a job.", "explanation": "更自然"},
            },
            "learnings": [
                {"title": "t", "rule": "r", "instances": [{"wrong": "creating job", "right": "creating a job"}], "examples": ["e"]}
            ],
        },
        "reply": None,
    }
    llm_call = _mock_llm(lambda msgs: json.dumps(report, ensure_ascii=False))
    case = {
        "id": "C-01",
        "input": "Correct the trigger_by field set up logic when creating job.",
        "expect": {
            "has_errors": True, "error_count_min": 1,
            "must_have": [{"fragment_contains": "creating job", "correction_contains": "a job", "category_expected": "grammar"}],
            "minimal_contains": "setup", "preserve_terms": ["trigger_by"], "learnings_min": 1,
        },
    }
    result = await run_case(llm_call, case)
    assert result["passed"] is True
    assert result["failures"] == []


async def test_run_case_llm_bad_json():
    llm_call = _mock_llm(lambda msgs: "not-json")
    case = {"id": "X", "input": "hello", "expect": {}}
    result = await run_case(llm_call, case)
    assert result["passed"] is False
    assert any("JSON" in f for f in result["failures"])


async def test_run_case_llm_returns_non_object_json():
    llm_call = _mock_llm(lambda msgs: "[1, 2, 3]")
    case = {"id": "X", "input": "hello", "expect": {}}
    result = await run_case(llm_call, case)
    assert result["passed"] is False
    assert any("对象" in f for f in result["failures"])


async def test_run_acceptance_aggregates():
    calls = {"n": 0}

    def responder(messages):
        calls["n"] += 1
        report = {
            "intent": "correction",
            "correction": {
                "has_errors": False, "errors": [],
                "rewrite": {"minimal": {"text": "ok", "explanation": ""}, "natural": {"text": "ok", "explanation": ""}},
                "learnings": [],
            },
            "reply": None,
        }
        return json.dumps(report)

    cases = [
        {"id": "A", "input": "a", "expect": {"has_errors": False, "error_count_min": 0, "must_have": [], "minimal_contains": "ok", "preserve_terms": [], "learnings_min": 0}},
        {"id": "B", "input": "b", "expect": {"has_errors": False, "error_count_min": 0, "must_have": [], "minimal_contains": "ok", "preserve_terms": [], "learnings_min": 0}},
    ]
    summary = await run_acceptance(_mock_llm(responder), cases)
    assert summary["total"] == 2
    assert summary["passed"] == 2
    assert summary["all_passed"] is True
