from app.core.config import Settings


def test_settings_tolerates_stale_llm_tuning_keys(monkeypatch):
    """历史 .env 可能残留 LLM_TEMPERATURE / LLM_ENABLE_THINKING，不能导致启动失败。"""
    monkeypatch.setenv("LLM_TEMPERATURE", "0")
    monkeypatch.setenv("LLM_ENABLE_THINKING", "false")
    settings = Settings()
    assert not hasattr(settings, "LLM_TEMPERATURE")
    assert not hasattr(settings, "LLM_ENABLE_THINKING")
