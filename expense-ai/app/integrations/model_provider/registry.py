"""Provider selection and construction.

The only place that maps a provider name to a concrete adapter and its settings.
Adding a provider means adding one entry here plus its settings fields.
"""

from __future__ import annotations

from pydantic import SecretStr

from app.core.config import ProviderName, Settings
from app.integrations.model_provider.anthropic_provider import AnthropicProvider
from app.integrations.model_provider.base import ModelProvider, ProviderConfig
from app.integrations.model_provider.errors import ProviderConfigurationError
from app.integrations.model_provider.fake import FakeModelProvider
from app.integrations.model_provider.gemini import GeminiProvider
from app.integrations.model_provider.openai_compatible import (
    DeepSeekProvider,
    MistralProvider,
    OpenAiProvider,
)

_PROVIDERS: dict[ProviderName, type[ModelProvider]] = {
    ProviderName.OPENAI: OpenAiProvider,
    ProviderName.ANTHROPIC: AnthropicProvider,
    ProviderName.MISTRAL: MistralProvider,
    ProviderName.DEEPSEEK: DeepSeekProvider,
    ProviderName.GEMINI: GeminiProvider,
    ProviderName.FAKE: FakeModelProvider,
}


def _secret_value(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret is not None else None


def resolve_provider_config(settings: Settings) -> ProviderConfig:
    """Resolve the selected provider's config, failing fast when credentials are absent."""
    provider = settings.llm_provider

    match provider:
        case ProviderName.OPENAI:
            model, base_url, api_key = (
                settings.openai_model,
                settings.openai_base_url,
                _secret_value(settings.openai_api_key),
            )
        case ProviderName.ANTHROPIC:
            model, base_url, api_key = (
                settings.anthropic_model,
                settings.anthropic_base_url,
                _secret_value(settings.anthropic_api_key),
            )
        case ProviderName.MISTRAL:
            model, base_url, api_key = (
                settings.mistral_model,
                settings.mistral_base_url,
                _secret_value(settings.mistral_api_key),
            )
        case ProviderName.DEEPSEEK:
            model, base_url, api_key = (
                settings.deepseek_model,
                settings.deepseek_base_url,
                _secret_value(settings.deepseek_api_key),
            )
        case ProviderName.GEMINI:
            model, base_url, api_key = (
                settings.gemini_model,
                settings.gemini_base_url,
                _secret_value(settings.gemini_api_key),
            )
        case ProviderName.FAKE:
            model, base_url, api_key = "fake-1", "", None
        case _:
            raise ProviderConfigurationError(f"Unsupported provider: {provider}")

    if provider is not ProviderName.FAKE and (api_key is None or not api_key.strip()):
        raise ProviderConfigurationError(f"Provider '{provider.value}' requires an API key")

    return ProviderConfig(
        name=provider.value,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        backoff_seconds=settings.llm_backoff_seconds,
    )


def build_provider(settings: Settings) -> ModelProvider:
    """Construct the configured provider adapter."""
    config = resolve_provider_config(settings)
    factory = _PROVIDERS[settings.llm_provider]
    return factory(config)  # type: ignore[call-arg]


def supported_providers() -> list[str]:
    return [provider.value for provider in _PROVIDERS]
