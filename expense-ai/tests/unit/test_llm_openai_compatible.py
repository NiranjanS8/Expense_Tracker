from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.integrations.model_provider.base import HttpModelProvider, ProviderConfig
from app.integrations.model_provider.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.integrations.model_provider.openai_compatible import (
    DeepSeekProvider,
    MistralProvider,
    OpenAiProvider,
)
from app.integrations.model_provider.types import (
    ChatMessage,
    ChatRequest,
    FinishReason,
    Role,
    ToolSpec,
)
from tests.conftest import final_response, sse_body, streamed_text

Responder = Callable[[httpx.Request], httpx.Response]


def build_provider(
    responder: Responder,
    *,
    provider_type: type[HttpModelProvider] = OpenAiProvider,
    max_retries: int = 0,
) -> HttpModelProvider:
    config = ProviderConfig(
        name=provider_type.name,
        model="gpt-4o-mini",
        base_url="https://openai.test/v1",
        api_key="test-key",
        timeout_seconds=1.0,
        max_retries=max_retries,
        backoff_seconds=0.0,
    )
    return provider_type(config, client=httpx.AsyncClient(transport=httpx.MockTransport(responder)))


async def test_openai_encodes_messages_tools_and_headers() -> None:
    captured: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
        )

    provider = build_provider(responder)
    await provider.complete(
        ChatRequest(
            messages=[ChatMessage(role=Role.USER, content="How much did I spend?")],
            tools=[ToolSpec(name="get_spending_summary", description="Summarise spending")],
            temperature=0.0,
            max_output_tokens=256,
        )
    )

    assert captured["url"] == "https://openai.test/v1/chat/completions"
    headers = captured["headers"]
    assert headers["authorization"] == "Bearer test-key"  # type: ignore[index]

    body = captured["body"]
    assert body["model"] == "gpt-4o-mini"  # type: ignore[index]
    assert body["messages"] == [{"role": "user", "content": "How much did I spend?"}]  # type: ignore[index]
    assert body["tools"] == [  # type: ignore[index]
        {
            "type": "function",
            "function": {
                "name": "get_spending_summary",
                "description": "Summarise spending",
                "parameters": {},
            },
        }
    ]
    assert body["temperature"] == 0.0  # type: ignore[index]
    assert body["max_tokens"] == 256  # type: ignore[index]


async def test_openai_decodes_tool_calls_and_usage() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_budget_status",
                                        "arguments": '{"month": "2026-04"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    response = await build_provider(responder).complete(ChatRequest(messages=[]))

    assert response.tool_calls[0].name == "get_budget_status"
    assert response.tool_calls[0].arguments == {"month": "2026-04"}
    assert response.finish_reason is FinishReason.TOOL_CALLS
    assert response.usage.total_tokens == 15


def test_tool_result_messages_include_tool_call_id() -> None:
    from app.integrations.model_provider.openai_compatible import _encode_message

    encoded = _encode_message(ChatMessage(role=Role.TOOL, content='{"total": 10}', tool_call_id="call_1"))

    assert encoded == {"role": "tool", "content": '{"total": 10}', "tool_call_id": "call_1"}


@pytest.mark.parametrize("provider_type", [OpenAiProvider, MistralProvider, DeepSeekProvider])
async def test_openai_compatible_family_shares_behaviour(provider_type: type[HttpModelProvider]) -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]},
        )

    response = await build_provider(responder, provider_type=provider_type).complete(
        ChatRequest(messages=[ChatMessage(role=Role.USER, content="hi")])
    )

    assert response.content == "hi"


async def test_authentication_failure_is_not_retried() -> None:
    calls = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(ProviderAuthenticationError):
        await build_provider(responder, max_retries=3).complete(ChatRequest(messages=[]))

    assert calls == 1


async def test_rate_limit_maps_to_provider_rate_limited() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    with pytest.raises(ProviderRateLimitedError):
        await build_provider(responder).complete(ChatRequest(messages=[]))


async def test_retryable_status_is_retried_then_succeeds() -> None:
    calls = 0

    def responder(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
        )

    response = await build_provider(responder, max_retries=1).complete(ChatRequest(messages=[]))

    assert response.content == "ok"
    assert calls == 2


async def test_exhausted_retries_surface_unavailable() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(ProviderUnavailableError):
        await build_provider(responder, max_retries=1).complete(ChatRequest(messages=[]))


def _stream_responder(*events: dict[str, Any] | str) -> Responder:
    body = sse_body(*events)

    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    return responder


async def test_openai_streams_content_deltas_then_the_assembled_response() -> None:
    responder = _stream_responder(
        {"model": "gpt-4o-mini", "choices": [{"delta": {"role": "assistant", "content": ""}}]},
        {"choices": [{"delta": {"content": "You spent "}}]},
        {"choices": [{"delta": {"content": "120.00."}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        "[DONE]",
    )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    assert streamed_text(chunks) == ["You spent ", "120.00."]
    assert final_response(chunks).content == "You spent 120.00."
    assert final_response(chunks).finish_reason is FinishReason.STOP


async def test_openai_reassembles_tool_call_arguments_split_across_events() -> None:
    # The arguments JSON arrives in two fragments that only parse once joined.
    opening_fragment = '{"mon'
    closing_fragment = 'th": "2026-04"}'

    responder = _stream_responder(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "function": {"name": "get_budget_status", "arguments": ""},
                            }
                        ]
                    }
                }
            ]
        },
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": opening_fragment}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": closing_fragment}}]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
    )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    response = final_response(chunks)
    assert streamed_text(chunks) == []
    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "get_budget_status"
    assert response.tool_calls[0].arguments == {"month": "2026-04"}
    assert response.finish_reason is FinishReason.TOOL_CALLS


async def test_openai_reads_usage_from_the_last_stream_event() -> None:
    responder = _stream_responder(
        {"choices": [{"delta": {"content": "ok"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}},
    )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    assert final_response(chunks).usage.total_tokens == 9


async def test_stream_usage_is_only_requested_where_the_endpoint_accepts_it() -> None:
    bodies: list[dict[str, Any]] = []

    def responder(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, content=sse_body({"choices": [{"delta": {}, "finish_reason": "stop"}]}))

    for provider_type in (OpenAiProvider, MistralProvider):
        async for _ in build_provider(responder, provider_type=provider_type).stream(
            ChatRequest(messages=[])
        ):
            pass

    assert bodies[0]["stream"] is True
    assert bodies[0]["stream_options"] == {"include_usage": True}
    assert bodies[1]["stream"] is True
    assert "stream_options" not in bodies[1]
