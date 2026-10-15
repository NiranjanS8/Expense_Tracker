"""Typed application settings loaded from the environment / ``.env``."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderName(StrEnum):
    """Selectable model providers. ``anthropic`` is Claude."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    FAKE = "fake"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    service_name: str = "expense-ai"
    app_env: str = "local"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    expense_tracker_base_url: str = "http://localhost:9090"
    expense_tracker_context_path: str = "/api"
    expense_tracker_timeout_seconds: float = Field(default=5.0, gt=0)

    identity_cache_ttl_seconds: int = Field(default=60, ge=0)

    max_request_bytes: int = Field(default=32_768, gt=0)
    chat_rate_limit_per_minute: int = Field(default=20, gt=0)
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    llm_provider: ProviderName = ProviderName.FAKE
    llm_timeout_seconds: float = Field(default=30.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    llm_backoff_seconds: float = Field(default=0.5, ge=0)
    llm_temperature: float = Field(default=0.0, ge=0, le=2)
    llm_max_output_tokens: int = Field(default=1024, gt=0, le=8192)

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com/v1"

    mistral_api_key: SecretStr | None = None
    mistral_model: str = "mistral-small-latest"
    mistral_base_url: str = "https://api.mistral.ai/v1"

    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"


@lru_cache
def get_settings() -> Settings:
    return Settings()
