"""Typed provider failures.

Adapters translate transport, HTTP and payload problems into these errors so the
workflow layer can behave deterministically and never fabricate a financial
result when a model call fails.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for model-provider failures."""


class ProviderConfigurationError(ProviderError):
    """The selected provider is missing credentials or configuration."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected our credentials."""


class ProviderRateLimitedError(ProviderError):
    """The provider rate limited the request."""


class ProviderTimeoutError(ProviderError):
    """The provider did not respond in time."""


class ProviderUnavailableError(ProviderError):
    """The provider returned a server error or is unreachable."""


class ProviderInvalidRequestError(ProviderError):
    """The provider rejected the request as malformed."""


class ProviderInvalidResponseError(ProviderError):
    """The provider returned a response we could not interpret."""
