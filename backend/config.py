from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "opencli-admin"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "sqlite+aiosqlite:///./opencli_admin.db"

    # Task execution mode: "local" (in-process asyncio) or "celery" (distributed)
    task_executor: Literal["local", "celery"] = "local"

    # Redis / Celery — only required when task_executor="celery"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # API Security
    api_key_enabled: bool = False
    api_key: str = ""

    # AI Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Webhooks
    webhook_secret: str = "change-me-webhook-secret"

    # Timezone
    default_timezone: str = "UTC"

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
