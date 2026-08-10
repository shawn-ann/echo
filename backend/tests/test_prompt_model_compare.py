from app.scripts.prompt_model_compare import _case_hit_rate, _summarize_output


def _mk_raw(errors, learnings_n=0):
    return json_dumps({"intent": "correction", "correction": {"has_errors": True, "errors": errors, "learnings": [{}] * learnings_n}})


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


def test_summarize_output_extracts():
    raw = json_dumps({"intent": "correction", "correction": {"has_errors": True, "errors": [{"category": "grammar", "error_type": "冠词缺失", "correction": "a job"}], "learnings": [{"t": 1}]}})
    s = _summarize_output(raw)
    assert len(s["errors"]) == 1
    assert s["errors"][0]["error_type"] == "冠词缺失"
    assert s["learnings"] == 1
    assert s["ok"] is True


def test_summarize_output_bad_json():
    s = _summarize_output("not-json")
    assert s["ok"] is False
    assert "非合法 JSON" in s["error"]


def test_case_hit_rate():
    cases = {
        "C-01": {"expect": {"must_have": [{"fragment_contains": "creating job"}, {"fragment_contains": "set up"}]}},
        "C-02": {"expect": {"must_have": [{"fragment_contains": "getting an error"}]}},
    }
    # C-01 命中 2/2（CI 子串匹配）
    summary = {"errors": [{"fragment": "creating job"}, {"fragment": "set up logic"}]}
    assert _case_hit_rate("C-01", summary, cases) == (2, 2)
    # C-01 部分命中 1/2
    summary2 = {"errors": [{"fragment": "creating job"}]}
    assert _case_hit_rate("C-01", summary2, cases) == (1, 2)
    # 无 must_have → (0, 0)
    assert _case_hit_rate("C-03", {"errors": []}, {"C-03": {"expect": {}}}) == (0, 0)
