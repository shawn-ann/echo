from app.prompts.coach_prompt import COACH_SYSTEM_PROMPT, build_coach_messages


def test_prompt_has_only_correction_json_contract():
    assert '"errors"' in COACH_SYSTEM_PROMPT
    assert '"rewrites"' in COACH_SYSTEM_PROMPT
    assert '"mode"' not in COACH_SYSTEM_PROMPT
    assert '"has_errors"' not in COACH_SYSTEM_PROMPT
    assert '"learnings"' not in COACH_SYSTEM_PROMPT


def test_prompt_only_defines_correction_responsibility():
    assert "## When to correct" in COACH_SYSTEM_PROMPT
    assert "Do you have any idea about this?" in COACH_SYSTEM_PROMPT
    assert "Two response formats" not in COACH_SYSTEM_PROMPT
    assert "plain Chinese text" not in COACH_SYSTEM_PROMPT
    assert "Mini example — follow-up" not in COACH_SYSTEM_PROMPT


def test_build_coach_messages_prepends_system_prompt():
    messages = build_coach_messages([{"role": "user", "content": "Hello."}])
    assert messages[0] == {"role": "system", "content": COACH_SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "Hello."}
