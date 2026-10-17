"""The streaming contract: the fallback, SSE decoding, and mid-stream failure."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from app.integrations.model_provider.base import (
    ModelProvider,
    ProviderConfig,
    decode_stream_event,
)
from app.integrations.model_provider.errors import (
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderUnavailableError,
)
from app.integrations.model_provider.openai_compatible import OpenAiProvider
from app.integrations.model_provider.types import ChatRequest, ChatResponse, TextDelta
from tests.conftest import final_response, sse_body, streamed_text

Responder = Callable[[httpx.Request], httpx.Response]


class _CompleteOnlyProvider(ModelProvider):
    """A provider with no native streaming: the default must still hold."""

    name = "complete-only"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(provider=self.name, model="m-1", content="whole answer")


async def test_a_provider_without_streaming_yields_one_whole_delta() -> None:
    chunks = [chunk async for chunk in _CompleteOnlyProvider().stream(ChatRequest(messages=[]))]

    assert streamed_text(chunks) == ["whole answer"]
    assert final_response(chunks).content == "whole answer"


async def test_a_completion_with_no_text_yields_only_the_completion() -> None:
    class _ToolOnlyProvider(_CompleteOnlyProvider):
        async def complete(self, request: ChatRequest) -> ChatResponse:
            return ChatResponse(provider=self.name, model="m-1", content=None)

    chunks = [chunk async for chunk in _ToolOnlyProvider().stream(ChatRequest(messages=[]))]

    assert streamed_text(chunks) == []
    assert final_response(chunks).content is None


@pytest.mark.parametrize("line", ["", "   ", ": keep-alive", "event: message_start", "id: 42"])
def test_lines_carrying_no_event_are_skipped(line: str) -> None:
    assert decode_stream_event(line) is None


@pytest.mark.parametrize("line", ["data: [DONE]", "data:", "data: "])
def test_the_end_of_stream_sentinel_carries_no_event(line: str) -> None:
    assert decode_stream_event(line) is None


def test_a_data_line_decodes_to_its_object() -> None:
    assert decode_stream_event('data: {"choices": []}') == {"choices": []}


def test_a_data_line_needs_no_space_after_the_colon() -> None:
    assert decode_stream_event('data:{"a":1}') == {"a": 1}


def test_an_undecodable_event_is_a_provider_error() -> None:
    with pytest.raises(ProviderInvalidResponseError):
        decode_stream_event("data: not json")


def build_provider(responder: Responder, *, max_retries: int = 0) -> OpenAiProvider:
    config = ProviderConfig(
        name="openai",
        model="gpt-4o-mini",
        base_url="https://openai.test/v1",
        api_key="test-key",
        timeout_seconds=1.0,
        max_retries=max_retries,
        backoff_seconds=0.0,
    )
    return OpenAiProvider(config, client=httpx.AsyncClient(transport=httpx.MockTransport(responder)))


class _InterruptedStream(httpx.AsyncByteStream):
    """Delivers one event, then drops the connection."""

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield sse_body({"choices": [{"delta": {"content": "half an answer"}}]})
        raise httpx.ReadError("connection dropped")

    async def aclose(self) -> None:
        return None


async def test_a_failure_after_the_first_event_is_terminal() -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, stream=_InterruptedStream())

    received: list[str] = []
    with pytest.raises(ProviderUnavailableError):
        async for chunk in build_provider(responder, max_retries=2).stream(ChatRequest(messages=[])):
            if isinstance(chunk, TextDelta):
                received.append(chunk.text)

    # Retrying would repeat text the caller already has.
    assert attempts == 1
    assert received == ["half an answer"]


async def test_a_failure_before_the_first_event_is_retried() -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(
            200,
            content=sse_body({"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}),
        )

    chunks = [
        chunk async for chunk in build_provider(responder, max_retries=1).stream(ChatRequest(messages=[]))
    ]

    assert attempts == 2
    assert final_response(chunks).content == "ok"


async def test_a_stream_rejected_for_credentials_is_not_retried() -> None:
    attempts = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(ProviderAuthenticationError):
        async for _ in build_provider(responder, max_retries=3).stream(ChatRequest(messages=[])):
            pass

    assert attempts == 1
