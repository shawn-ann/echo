from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"
    SESSION_TTL_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"

    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_MODE: str = ""  # ""=真实调用（需配置）; "mock"=测试/演示用确定性 Mock
    # 思考参数名：chat_template_kwargs（DeepSeek）/ enable_thinking（百炼 Qwen/GLM）/ thinking（Anthropic 风格）
    LLM_THINKING_PARAM: str = "chat_template_kwargs"
    # glm-5.3 等“仅思考模式”的模型必须固定为 True
    LLM_THINKING_ALWAYS_ON: bool = False
    # 流式纠错实验端点：默认关闭，避免误部署到公网；本地联调显式设为 true
    STREAM_MVP_ENABLED: bool = False
    CONTEXT_LIMIT: int = 40
    CORRECTION_STYLE: str = "casual"  # 纠错场景：casual（日常/职场口语，默认）/ formal（正式书面）

    # MVP 固定种子账号
    SEED_USERNAME: str = "shawn"
    SEED_PASSWORD: str = "shawn!QAZ1qaz"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
