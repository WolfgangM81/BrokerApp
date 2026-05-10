"""Worker configuration. Same env contract as the API where possible."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    postgres_user: str = Field(default="brokerapp")
    postgres_password: str = Field(default="brokerapp")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="brokerapp")

    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    # Internal API endpoint for callbacks (Phase 4+ when worker → API
    # writes appear). Phase 1 writes directly to DB.
    api_base_url: str = Field(default="http://api.brokerapp:8000")
    internal_token: str = Field(default="")

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings()
