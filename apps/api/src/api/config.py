"""Application configuration. All settings come from env vars."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known-insecure defaults. The dev compose stack uses these; any non-dev
# environment that still has them is misconfigured and must fail loudly at
# startup rather than silently exposing a default-credential database.
_INSECURE_DEFAULTS = {
    "postgres_password": "brokerapp",
}


class Settings(BaseSettings):
    """Settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["dev", "staging", "production"] = Field(default="dev")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="API_LOG_LEVEL"
    )

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")  # noqa: S104
    api_port: int = Field(default=8000, alias="API_PORT")
    api_cors_origins: str = Field(default="http://localhost:3000", alias="API_CORS_ORIGINS")

    postgres_user: str = Field(default="brokerapp")
    postgres_password: str = Field(default="brokerapp")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="brokerapp")

    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    authentik_issuer: str = Field(default="")
    authentik_audience: str = Field(default="brokerapp")
    authentik_jwks_url: str = Field(default="")

    @model_validator(mode="after")
    def _reject_insecure_defaults_in_non_dev(self) -> Settings:
        """Refuse to start in staging/production with dev-default secrets."""
        if self.environment == "dev":
            return self
        offending: list[str] = []
        for attr, default in _INSECURE_DEFAULTS.items():
            if getattr(self, attr) == default:
                offending.append(attr)
        if offending:
            joined = ", ".join(offending)
            raise ValueError(
                f"Refusing to start in environment={self.environment!r} with "
                f"insecure default value(s) for: {joined}. Override via env vars."
            )
        return self

    @property
    def database_url(self) -> PostgresDsn:
        return PostgresDsn(
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
