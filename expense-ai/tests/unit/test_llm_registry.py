from __future__ import annotations

import pytest

from app.core.config import ProviderName, Settings
from app.integrations.model_provider import (
    FakeModelProvider,
    ProviderConfigurationError,
    build_provider,
    resolve_provider_config,
    supported_providers,
)
from app.integrations.model_provider.anthropic_provider import AnthropicProvider
from app.integrations.model_provider.gemini import GeminiProvider
from app.integrations.model_provider.openai_compatible import (
    DeepSeekProvider,
    MistralProvider,
    OpenAiProvider,
)


def test_all_requested_providers_are_supported() -> None:
    assert {"openai", "anthropic", "mistral", "deepseek", "gemini"} <= set(supported_providers())


def build_settings(provider: ProviderName, **overrides: object) -> Settings:
    """Build settings deterministically, bypassing the environment."""
    return Settings.model_validate({"_env_file": None, "llm_provider": provider, **overrides})


@pytest.mark.parametrize(
    ("provider", "expected_model", "expected_base_url"),
    [
        (ProviderName.OPENAI, "gpt-4o-mini", "https://api.openai.com/v1"),
        (ProviderName.ANTHROPIC, "claude-3-5-haiku-latest", "https://api.anthropic.com/v1"),
        (ProviderName.MISTRAL, "mistral-small-latest", "https://api.mistral.ai/v1"),
        (ProviderName.DEEPSEEK, "deepseek-chat", "https://api.deepseek.com/v1"),
        (ProviderName.GEMINI, "gemini-2.0-flash", "https://generativelanguage.googleapis.com/v1beta"),
    ],
)
def test_provider_config_resolves_model_and_endpoint(
    provider: ProviderName,
    expected_model: str,
    expected_base_url: str,
) -> None:
    settings = build_settings(provider, **{f"{provider.value}_api_key": "test-key"})

    config = resolve_provider_config(settings)

    assert config.name == provider.value
    assert config.model == expected_model
    assert config.base_url == expected_base_url
    assert config.api_key == "test-key"


@pytest.mark.parametrize(
    "provider",
    [
        ProviderName.OPENAI,
        ProviderName.ANTHROPIC,
        ProviderName.MISTRAL,
        ProviderName.DEEPSEEK,
        ProviderName.GEMINI,
    ],
)
def test_provider_config_requires_an_api_key(provider: ProviderName) -> None:
    settings = build_settings(provider)

    with pytest.raises(ProviderConfigurationError):
        resolve_provider_config(settings)


def test_fake_provider_needs_no_credentials() -> None:
    settings = Settings(_env_file=None, llm_provider=ProviderName.FAKE)

    provider = build_provider(settings)

    assert isinstance(provider, FakeModelProvider)


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        (ProviderName.OPENAI, OpenAiProvider),
        (ProviderName.ANTHROPIC, AnthropicProvider),
        (ProviderName.MISTRAL, MistralProvider),
        (ProviderName.DEEPSEEK, DeepSeekProvider),
        (ProviderName.GEMINI, GeminiProvider),
    ],
)
def test_build_provider_selects_the_right_adapter(
    provider: ProviderName,
    expected_type: type[object],
) -> None:
    settings = build_settings(provider, **{f"{provider.value}_api_key": "test-key"})

    assert isinstance(build_provider(settings), expected_type)
