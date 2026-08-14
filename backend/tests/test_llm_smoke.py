from app.scripts.llm_smoke import build_messages, run_smoke


def test_build_messages_uses_system_prompt():
    msgs = build_messages("She go to school yesterday.", "casual")
    assert msgs[0]["role"] == "system"
    assert "correction" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "She go to school yesterday."}


async def test_run_smoke_with_fake_llm():
    async def fake_llm(messages):
        return '{"has_errors":true,"errors":[{"error_type":"时态错误","fragment":"go","explanation":"","correction":"went"}],"rewrite":{"minimal":{"text":"ok","note":""},"natural":{"text":"ok","note":""}},"learnings":[]}'

    result = await run_smoke(fake_llm, "She go to school yesterday.", "casual")
    assert result["ok"] is True
    assert "correction" in result["raw"]
