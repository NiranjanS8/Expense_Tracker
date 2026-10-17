from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from app.integrations.model_provider.anthropic_provider import AnthropicProvider
from app.integrations.model_provider.base import ProviderConfig
from app.integrations.model_provider.types import (
    ChatMessage,
    ChatRequest,
    FinishReason,
    Role,
    ToolCall,
    ToolSpec,
)
from tests.conftest import final_response, sse_body, streamed_text

Responder = Callable[[httpx.Request], httpx.Response]


def build_provider(responder: Responder) -> AnthropicProvider:
    config = ProviderConfig(
        name="anthropic",
        model="claude-3-5-haiku-latest",
        base_url="https://anthropic.test/v1",
        api_key="test-key",
        timeout_seconds=1.0,
        max_retries=0,
        backoff_seconds=0.0,
    )
    return AnthropicProvider(config, client=httpx.AsyncClient(transport=httpx.MockTransport(responder)))


async def test_anthropic_extracts_system_prompt_and_sends_version_header() -> None:
    captured: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-3-5-haiku-latest",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 3, "output_tokens": 4},
            },
        )

    await build_provider(responder).complete(
        ChatRequest(
            messages=[
                ChatMessage(role=Role.SYSTEM, content="You are a finance assistant."),
                ChatMessage(role=Role.USER, content="Hi"),
            ],
            tools=[ToolSpec(name="get_goal_progress", description="Goals", parameters={"type": "object"})],
            max_output_tokens=512,
        )
    )

    assert captured["url"] == "https://anthropic.test/v1/messages"
    headers = captured["headers"]
    assert headers["x-api-key"] == "test-key"  # type: ignore[index]
    assert headers["anthropic-version"] == "2023-06-01"  # type: ignore[index]

    body = captured["body"]
    assert body["system"] == "You are a finance assistant."  # type: ignore[index]
    assert body["messages"] == [{"role": "user", "content": "Hi"}]  # type: ignore[index]
    assert body["max_tokens"] == 512  # type: ignore[index]
    assert body["tools"] == [  # type: ignore[index]
        {"name": "get_goal_progress", "description": "Goals", "input_schema": {"type": "object"}}
    ]


async def test_anthropic_encodes_assistant_tool_calls_and_tool_results() -> None:
    captured: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn"},
        )

    await build_provider(responder).complete(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=Role.ASSISTANT,
                    tool_calls=[
                        ToolCall(id="tu_1", name="get_budget_status", arguments={"month": "2026-04"})
                    ],
                ),
                ChatMessage(role=Role.TOOL, content='{"spent": 100}', tool_call_id="tu_1"),
            ]
        )
    )

    messages = captured["body"]["messages"]  # type: ignore[index]
    assert messages[0] == {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "tu_1", "name": "get_budget_status", "input": {"month": "2026-04"}}
        ],
    }
    assert messages[1] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": '{"spent": 100}'}],
    }


async def test_anthropic_decodes_tool_use_blocks_and_usage() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "claude-3-5-haiku-latest",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {"type": "tool_use", "id": "toolu_9", "name": "get_recurring_expenses", "input": {}},
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 12, "output_tokens": 8},
            },
        )

    response = await build_provider(responder).complete(ChatRequest(messages=[]))

    assert response.provider == "anthropic"
    assert response.content == "Let me check."
    assert response.tool_calls[0].id == "toolu_9"
    assert response.tool_calls[0].name == "get_recurring_expenses"
    assert response.finish_reason is FinishReason.TOOL_CALLS
    assert response.usage.total_tokens == 20


async def test_anthropic_streams_text_deltas_and_usage() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body(
                {
                    "type": "message_start",
                    "message": {
                        "model": "claude-3-5-haiku-latest",
                        "usage": {"input_tokens": 12},
                    },
                },
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "You spent "},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "120.00."},
                },
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": 6},
                },
                {"type": "message_stop"},
            ),
        )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    assert streamed_text(chunks) == ["You spent ", "120.00."]
    assert final_response(chunks).content == "You spent 120.00."
    assert final_response(chunks).usage.total_tokens == 18
    assert final_response(chunks).finish_reason is FinishReason.STOP


async def test_anthropic_reassembles_tool_use_input_split_across_events() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {
                        "type": "tool_use",
                        "id": "toolu_9",
                        "name": "get_recurring_expenses",
                        "input": {},
                    },
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": '{"month"'},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": ': "2026-04"}'},
                },
                {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
            ),
        )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    response = final_response(chunks)
    assert response.tool_calls[0].id == "toolu_9"
    assert response.tool_calls[0].name == "get_recurring_expenses"
    assert response.tool_calls[0].arguments == {"month": "2026-04"}
    assert response.finish_reason is FinishReason.TOOL_CALLS
