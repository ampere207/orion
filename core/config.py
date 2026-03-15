from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Orion"
    app_env: str = "development"
    log_level: str = "INFO"
    workflow_max_retries: int = 3
    max_concurrent_tasks: int = 4
    workflow_result_poll_interval_seconds: float = 0.2
    workflow_result_timeout_seconds: float = 90.0

    gemini_api_key: str = ""
    gemini_api_key_fallback: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    rabbitmq_url: str = "amqp://guest:guest@localhost/"
    postgres_url: str = "postgresql+asyncpg://orion:orion@localhost:5432/orion"
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
