from app.prompts.coach_prompt import COACH_SYSTEM_PROMPT, build_coach_messages


def test_routing_prefers_draft_even_with_trailing_question():
    assert "Substantial English draft" in COACH_SYSTEM_PROMPT
    assert "Do you have any idea about this?" in COACH_SYSTEM_PROMPT
    assert "prefer `correct`" in COACH_SYSTEM_PROMPT
    assert "Interrogative form alone does not decide" in COACH_SYSTEM_PROMPT


def test_build_coach_messages_prepends_system_prompt():
    messages = build_coach_messages([{"role": "user", "content": "Hello."}])
    assert messages[0] == {"role": "system", "content": COACH_SYSTEM_PROMPT}
    assert messages[1] == {"role": "user", "content": "Hello."}
