"""The model-provider contract and shared HTTP behaviour.

To add a provider: subclass :class:`ModelProvider` (usually
:class:`HttpModelProvider`), register it in ``registry.py``, and add its settings.
No other module needs to change.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from app.integrations.model_provider.errors import (
    ProviderAuthenticationError,
    ProviderInvalidRequestError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.integrations.model_provider.types import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    base_url: str
    api_key: str | None
    timeout_seconds: float
    max_retries: int
    backoff_seconds: float


class ModelProvider(ABC):
    """Abstract model provider. Implementations must never leak credentials."""

    name: ClassVar[str]

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Run a single, non-streaming completion (optionally with tool calls)."""

    async def aclose(self) -> None:
        return None


class HttpModelProvider(ModelProvider):
    """Shared retry, timeout and error-mapping for HTTP-based providers."""

    name: ClassVar[str] = "http"

    def __init__(self, config: ProviderConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds, connect=min(config.timeout_seconds, 5.0))
        )

    @property
    def model(self) -> str:
        return self._config.model

    async def _post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        url = f"{self._config.base_url.rstrip('/')}{path}"
        attempts = self._config.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await self._client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException:
                last_error = ProviderTimeoutError(f"{self.name} timed out")
                logger.warning("event=provider_timeout provider=%s attempt=%s", self.name, attempt + 1)
                await self._backoff(attempt)
                continue
            except httpx.HTTPError as exception:
                last_error = ProviderUnavailableError(f"{self.name} is unreachable")
                logger.warning(
                    "event=provider_transport_error provider=%s error=%s",
                    self.name,
                    type(exception).__name__,
                )
                await self._backoff(attempt)
                continue

            if response.status_code in (401, 403):
                raise ProviderAuthenticationError(f"{self.name} rejected the credentials")

            if response.status_code in _RETRYABLE_STATUS:
                last_error = self._map_error_status(response.status_code)
                await self._backoff(attempt)
                continue

            if response.status_code >= 400:
                raise ProviderInvalidRequestError(f"{self.name} rejected the request")

            try:
                decoded = response.json()
            except ValueError as exception:
                logger.warning("event=provider_invalid_json provider=%s", self.name)
                raise ProviderInvalidResponseError(f"{self.name} returned invalid JSON") from exception

            if not isinstance(decoded, dict):
                logger.warning("event=provider_unexpected_payload provider=%s", self.name)
                raise ProviderInvalidResponseError(f"{self.name} returned a non-object JSON body")

            return decoded

        raise last_error or ProviderUnavailableError(f"{self.name} request failed")

    async def _backoff(self, attempt: int) -> None:
        if self._config.backoff_seconds <= 0:
            return
        await asyncio.sleep(self._config.backoff_seconds * (2**attempt))

    def _map_error_status(self, status: int) -> Exception:
        if status == 429:
            return ProviderRateLimitedError(f"{self.name} rate limited the request")
        return ProviderUnavailableError(f"{self.name} returned status {status}")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def require_api_key(config: ProviderConfig) -> str:
    if config.api_key is None or not config.api_key.strip():
        from app.integrations.model_provider.errors import ProviderConfigurationError

        raise ProviderConfigurationError(f"{config.name} requires an API key")
    return config.api_key
