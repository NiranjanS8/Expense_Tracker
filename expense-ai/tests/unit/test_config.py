from __future__ import annotations

import pytest

from app.core.config import ProviderName, Settings


def test_settings_default_to_fake_provider_and_safe_limits() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider is ProviderName.FAKE
    assert settings.max_request_bytes == 32_768
    assert settings.identity_cache_ttl_seconds == 60
    assert settings.cors_allow_origins == ["http://localhost:5173"]


def test_settings_expose_all_requested_providers() -> None:
    values = {provider.value for provider in ProviderName}

    assert {"openai", "anthropic", "mistral", "deepseek", "gemini"} <= values


def test_settings_read_provider_selection_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    settings = Settings(_env_file=None)

    assert settings.llm_provider is ProviderName.GEMINI
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "test-key"


def test_secret_values_are_not_exposed_in_repr() -> None:
    settings = Settings(_env_file=None, openai_api_key="super-secret")

    assert "super-secret" not in repr(settings)
