from app.scripts.prompt_model_compare import _case_hit_rate, _summarize_output


def _mk_raw(errors):
    return json_dumps({"intent": "correction", "correction": {"has_errors": True, "errors": errors}})


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


def test_summarize_output_extracts():
    raw = json_dumps({"intent": "correction", "correction": {"errors": [{"category": "冠词缺失", "correction": "a job"}]}})
    s = _summarize_output(raw)
    assert len(s["errors"]) == 1
    assert s["errors"][0]["category"] == "冠词缺失"
    assert s["ok"] is True


def test_summarize_output_legacy_english_category_falls_back():
    # 旧产物：category 是英文枚举 grammar，真实类型在 error_type
    raw = json_dumps({"intent": "correction", "correction": {"errors": [{"category": "grammar", "error_type": "冠词缺失", "correction": "a job"}]}})
    s = _summarize_output(raw)
    assert s["errors"][0]["category"] == "冠词缺失"


def test_summarize_output_bad_json():
    s = _summarize_output("not-json")
    assert s["ok"] is False
    assert "非合法 JSON" in s["error"]


def test_case_hit_rate():
    cases = {
        "C-01": {"expect": {"must_have": [{"fragment_contains": "creating job"}, {"fragment_contains": "set up"}]}},
        "C-02": {"expect": {"must_have": [{"fragment_contains": "getting an error"}]}},
    }
    # 内容词匹配：golden "creating job" → creating/job，LLM "when creating a job" 含两者 → 命中
    summary = {"errors": [{"fragment": "when creating a job"}]}
    assert _case_hit_rate("C-01", summary, cases) == (1, 2)
    # "set up" → 内容词 set/up，"setup" 含 "set" 子串 → 命中
    summary2 = {"errors": [{"fragment": "when creating a job"}, {"fragment": "setup"}]}
    assert _case_hit_rate("C-01", summary2, cases) == (2, 2)
    # "getting an error" → getting/error，"Are you getting an error?" 含两者 → 命中
    summary3 = {"errors": [{"fragment": "Are you getting an error?"}]}
    assert _case_hit_rate("C-02", summary3, cases) == (1, 1)
    # 无 must_have → (0, 0)
    assert _case_hit_rate("C-03", {"errors": []}, {"C-03": {"expect": {}}}) == (0, 0)
