"""Abstract model-provider layer: one interface, five providers, plus a fake.

Import public contract types from here:

    from app.integrations.model_provider import ChatRequest, ModelProvider, build_provider
"""

from app.integrations.model_provider.base import ModelProvider, ProviderConfig, require_api_key
from app.integrations.model_provider.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.integrations.model_provider.fake import FakeModelProvider
from app.integrations.model_provider.registry import (
    build_provider,
    resolve_provider_config,
    supported_providers,
)
from app.integrations.model_provider.types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Completion,
    FinishReason,
    ModelStreamChunk,
    Role,
    TextDelta,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "Completion",
    "FakeModelProvider",
    "FinishReason",
    "ModelProvider",
    "ModelStreamChunk",
    "ProviderAuthenticationError",
    "ProviderConfig",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderInvalidRequestError",
    "ProviderInvalidResponseError",
    "ProviderRateLimitedError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "Role",
    "TextDelta",
    "TokenUsage",
    "ToolCall",
    "ToolSpec",
    "build_provider",
    "require_api_key",
    "resolve_provider_config",
    "supported_providers",
]
