from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"
    SESSION_TTL_DAYS: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"

    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_MODE: str = ""  # ""=真实调用（需配置）; "mock"=测试/演示用确定性 Mock
    LLM_TEMPERATURE: float = 0
    LLM_ENABLE_THINKING: bool = False
    CONTEXT_LIMIT: int = 40
    CORRECTION_STYLE: str = "casual"  # 纠错场景：casual（日常/职场口语，默认）/ formal（正式书面）

    # MVP 固定种子账号
    SEED_USERNAME: str = "demo"
    SEED_PASSWORD: str = "demo1234"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
