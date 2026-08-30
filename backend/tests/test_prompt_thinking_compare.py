from app.scripts.prompt_thinking_compare import _summarize_result, write_compare


def _sample_summary(thinking, elapsed, outputs):
    return {
        "total": len(outputs),
        "elapsed": elapsed,
        "thinking": thinking,
        "model": "test-model",
        "style": "casual",
        "prompt": "p",
        "results": [
            {"id": f"C-0{i+1}", "input": f"in{i+1}", "output": out, "elapsed": 10.0, "error": None}
            for i, out in enumerate(outputs)
        ],
    }


def test_summarize_result_extracts_errors():
    raw = '{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"时态错误","correction":"went"}]}}'
    s = _summarize_result(raw)
    assert len(s["errors"]) == 1
    assert s["errors"][0]["error_type"] == "时态错误"


def test_summarize_result_bad_json():
    s = _summarize_result("not-json")
    assert "非合法 JSON" in s["error"]


def test_write_compare_generates_report(tmp_path):
    on_out = '{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"时态错误","correction":"went"}]}}'
    off_out = '{"intent":"correction","correction":{"has_errors":true,"errors":[{"category":"grammar","error_type":"时态错误","correction":"went"}]}}'
    on = _sample_summary("enabled", 100.0, [on_out])
    off = _sample_summary("disabled", 60.0, [off_out])
    out_path = tmp_path / "compare.md"
    result = write_compare(on, off, str(out_path))
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "思考模式对比" in text
    assert "100.0" in text and "60.0" in text
    assert "错误识别一致" in text
