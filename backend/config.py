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

    # Collection mode:
    # local — default; API directly drives Chrome containers in the same Docker network
    # agent — distributed edge nodes; collection is dispatched to remote agent servers
    #         each agent runs opencli locally and returns results via HTTP or WS
    collection_mode: Literal["local", "agent"] = "local"

    # Agent pool: comma-separated agent/CDP endpoint URLs.
    # Each entry is a Chrome agent node (local or remote).
    # Single-instance fallback when agent_pool_endpoints is empty.
    opencli_cdp_endpoint: str = "http://agent-1:19222"
    # Multi-agent pool: overrides opencli_cdp_endpoint when set.
    # e.g. http://agent-1:19222,http://agent-2:19222,http://192.168.1.100:19222
    agent_pool_endpoints: str = ""
    # noVNC base port for the first agent instance (agent-1). Additional
    # instances use base+1, base+2, …  Matches docker-compose NOVNC_PORT.
    novnc_base_port: int = 3010

    @property
    def cdp_endpoints(self) -> list[str]:
        if self.agent_pool_endpoints.strip():
            return [ep.strip() for ep in self.agent_pool_endpoints.split(",") if ep.strip()]
        return [self.opencli_cdp_endpoint]

    # Collect timeouts (seconds)
    # opencli subprocess execution timeout (local mode and agent-side)
    opencli_timeout: int = 120
    # HTTP dispatch timeout when center POSTs to a LAN agent (should be > opencli_timeout)
    agent_http_timeout: int = 130
    # WS dispatch timeout when center sends a task over a reverse WS channel
    agent_ws_timeout: int = 130

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
