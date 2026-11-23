"""Typed application settings. All secrets come from environment variables only."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    log_level: str = "INFO"

    # Database roles: see scripts/create_db_roles.sql
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://merchant_app:unset@localhost:5432/merchant_analytics")
    )
    analytics_database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://analytics_ro:unset@localhost:5432/merchant_analytics")
    )

    # Authentication
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "merchant-analytics"
    jwt_audience: str = "merchant-analytics-api"
    jwt_algorithm: str = "HS256"
    jwt_leeway_seconds: int = 30

    # Jev. Thresholds are provisional defaults, to be calibrated from the evaluation report.
    typesafe_api_key: SecretStr | None = None
    typesafe_default_model: str = "jev-latest"
    typesafe_timeout_seconds: float = 10.0
    jev_scope_min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    jev_tool_min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    jev_risk_block_threshold: float = Field(default=0.50, ge=0.0, le=1.0)

    # LLM interaction layer (provider-agnostic adapter; Anthropic implemented)
    llm_provider: str = "anthropic"
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 20.0
    llm_max_tokens: int = 800

    # Limits and policy
    rate_limit_per_minute: int = Field(default=20, ge=1)
    max_message_chars: int = Field(default=1000, ge=1, le=4000)
    max_date_span_days: int = Field(default=366, ge=1, le=732)
    disabled_capabilities: str = ""

    @field_validator("disabled_capabilities")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @property
    def disabled_capability_names(self) -> frozenset[str]:
        return frozenset(part.strip() for part in self.disabled_capabilities.split(",") if part.strip())

    @property
    def jev_configured(self) -> bool:
        return self.typesafe_api_key is not None and bool(self.typesafe_api_key.get_secret_value())

    @property
    def llm_configured(self) -> bool:
        return self.anthropic_api_key is not None and bool(self.anthropic_api_key.get_secret_value())

    @property
    def auth_configured(self) -> bool:
        return self.jwt_secret is not None and len(self.jwt_secret.get_secret_value()) >= 32


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
