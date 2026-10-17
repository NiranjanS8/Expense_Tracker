"""The model-provider contract and shared HTTP behaviour.

To add a provider: subclass :class:`ModelProvider` (usually
:class:`HttpModelProvider`), register it in ``registry.py``, and add its settings.
No other module needs to change.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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
from app.integrations.model_provider.types import (
    ChatRequest,
    ChatResponse,
    Completion,
    ModelStreamChunk,
    TextDelta,
    ToolCall,
)

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

    async def stream(self, request: ChatRequest) -> AsyncIterator[ModelStreamChunk]:
        """Stream a completion as content deltas followed by the assembled response.

        The default delegates to :meth:`complete`, so a provider with no native
        streaming still honours the contract with one whole-text delta. Adapters
        that can stream override this and decode their own wire format.
        """
        response = await self.complete(request)
        if response.content:
            yield TextDelta(text=response.content)
        yield Completion(response=response)

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

    async def _stream_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> AsyncIterator[dict[str, Any]]:
        """POST and yield the decoded body of each server-sent ``data:`` line.

        Retries follow :meth:`_post_json`, with one addition: once an event has
        been handed to the caller a retry would repeat text the caller already
        has, so a failure after the first event is terminal.
        """
        url = f"{self._config.base_url.rstrip('/')}{path}"
        attempts = self._config.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            delivered = False
            try:
                async with self._client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code in (401, 403):
                        raise ProviderAuthenticationError(f"{self.name} rejected the credentials")

                    if response.status_code in _RETRYABLE_STATUS:
                        await response.aread()
                        last_error = self._map_error_status(response.status_code)
                        await self._backoff(attempt)
                        continue

                    if response.status_code >= 400:
                        await response.aread()
                        raise ProviderInvalidRequestError(f"{self.name} rejected the request")

                    async for line in response.aiter_lines():
                        event = decode_stream_event(line)
                        if event is None:
                            continue
                        delivered = True
                        yield event
            except (httpx.TimeoutException, httpx.HTTPError) as exception:
                if delivered:
                    logger.warning(
                        "event=provider_stream_interrupted provider=%s error=%s",
                        self.name,
                        type(exception).__name__,
                    )
                    raise ProviderUnavailableError(
                        f"{self.name} failed part-way through the response"
                    ) from exception
                last_error = (
                    ProviderTimeoutError(f"{self.name} timed out")
                    if isinstance(exception, httpx.TimeoutException)
                    else ProviderUnavailableError(f"{self.name} is unreachable")
                )
                logger.warning(
                    "event=provider_transport_error provider=%s error=%s",
                    self.name,
                    type(exception).__name__,
                )
                await self._backoff(attempt)
                continue
            return

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


_STREAM_DONE = "[DONE]"


def decode_stream_event(line: str) -> dict[str, Any] | None:
    """Read the JSON object out of one server-sent-event line.

    Returns ``None`` for blank lines, comments, ``event:``/``id:`` fields and the
    ``[DONE]`` sentinel that OpenAI-compatible providers use to end a stream.
    """
    stripped = line.strip()
    if not stripped.startswith("data:"):
        return None

    payload = stripped[len("data:") :].strip()
    if not payload or payload == _STREAM_DONE:
        return None

    try:
        decoded = json.loads(payload)
    except ValueError as exception:
        logger.warning("event=provider_invalid_stream_event")
        raise ProviderInvalidResponseError("provider sent an undecodable stream event") from exception

    return decoded if isinstance(decoded, dict) else None


def decode_json_object(raw: Any) -> dict[str, Any]:
    """Read a JSON object a provider sent either inline or as a string."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        decoded = json.loads(raw)
    except ValueError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def accumulate_tool_call(
    partials: dict[int, dict[str, Any]],
    *,
    index: Any,
    call_id: Any = None,
    name: Any = None,
    arguments: Any = None,
) -> None:
    """Merge one streamed tool-call fragment into ``partials``, keyed by index.

    Adapters extract these fields from their own wire format: OpenAI nests the
    name and arguments under ``function`` and repeats the index on every
    fragment, while Anthropic names the call once and then appends argument
    fragments. A fragment with no usable index is treated as the first call.
    """
    entry = partials.setdefault(
        index if isinstance(index, int) else 0, {"id": "", "name": "", "arguments": ""}
    )
    if isinstance(call_id, str) and call_id:
        entry["id"] = call_id
    if isinstance(name, str) and name:
        entry["name"] = name
    if isinstance(arguments, str) and arguments:
        entry["arguments"] += arguments


def assemble_tool_calls(partials: dict[int, dict[str, Any]], *, id_prefix: str) -> list[ToolCall]:
    """Turn accumulated stream deltas into complete calls, in arrival order."""
    return [
        ToolCall(
            id=str(entry["id"]) or f"{id_prefix}{index}",
            name=str(entry["name"]),
            arguments=decode_json_object(entry["arguments"]),
        )
        for index, entry in sorted(partials.items())
    ]
