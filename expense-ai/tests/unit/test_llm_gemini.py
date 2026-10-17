from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from app.integrations.model_provider.base import ProviderConfig
from app.integrations.model_provider.gemini import GeminiProvider
from app.integrations.model_provider.types import (
    ChatMessage,
    ChatRequest,
    FinishReason,
    Role,
    ToolSpec,
)
from tests.conftest import final_response, sse_body, streamed_text

Responder = Callable[[httpx.Request], httpx.Response]

_FAKE_KEY = "gemini-test-key"


def build_provider(responder: Responder) -> GeminiProvider:
    config = ProviderConfig(
        name="gemini",
        model="gemini-2.0-flash",
        base_url="https://gemini.test/v1beta",
        api_key=_FAKE_KEY,
        timeout_seconds=1.0,
        max_retries=0,
        backoff_seconds=0.0,
    )
    return GeminiProvider(config, client=httpx.AsyncClient(transport=httpx.MockTransport(responder)))


async def test_gemini_uses_header_key_and_never_leaks_it_in_the_url() -> None:
    captured: dict[str, str] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key_header"] = request.headers["x-goog-api-key"]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}]},
        )

    await build_provider(responder).complete(
        ChatRequest(messages=[ChatMessage(role=Role.USER, content="hi")])
    )

    assert captured["url"] == "https://gemini.test/v1beta/models/gemini-2.0-flash:generateContent"
    assert _FAKE_KEY not in captured["url"]
    assert captured["key_header"] == _FAKE_KEY


async def test_gemini_encodes_system_instruction_and_tools() -> None:
    captured: dict[str, object] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    await build_provider(responder).complete(
        ChatRequest(
            messages=[
                ChatMessage(role=Role.SYSTEM, content="Be concise."),
                ChatMessage(role=Role.USER, content="Hi"),
            ],
            tools=[ToolSpec(name="get_goal_progress", description="Goals", parameters={"type": "object"})],
            max_output_tokens=256,
        )
    )

    body = captured["body"]
    assert body["systemInstruction"] == {"parts": [{"text": "Be concise."}]}  # type: ignore[index]
    assert body["contents"] == [{"role": "user", "parts": [{"text": "Hi"}]}]  # type: ignore[index]
    assert body["tools"] == [  # type: ignore[index]
        {
            "functionDeclarations": [
                {"name": "get_goal_progress", "description": "Goals", "parameters": {"type": "object"}}
            ]
        }
    ]
    assert body["generationConfig"]["maxOutputTokens"] == 256  # type: ignore[index]


async def test_gemini_decodes_function_calls_with_synthetic_ids() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "modelVersion": "gemini-2.0-flash",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"functionCall": {"name": "get_budget_status", "args": {"month": "2026-04"}}}
                            ]
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 4, "totalTokenCount": 13},
            },
        )

    response = await build_provider(responder).complete(ChatRequest(messages=[]))

    assert response.provider == "gemini"
    assert response.tool_calls[0].name == "get_budget_status"
    assert response.tool_calls[0].arguments == {"month": "2026-04"}
    assert response.tool_calls[0].id
    assert response.finish_reason is FinishReason.TOOL_CALLS
    assert response.usage.total_tokens == 13


async def test_gemini_streams_parts_from_an_sse_stream() -> None:
    captured: dict[str, str] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            content=sse_body(
                {"candidates": [{"content": {"parts": [{"text": "You spent "}]}}]},
                {"candidates": [{"content": {"parts": [{"text": "120.00."}]}, "finishReason": "STOP"}]},
                {
                    "usageMetadata": {
                        "promptTokenCount": 9,
                        "candidatesTokenCount": 4,
                        "totalTokenCount": 13,
                    }
                },
            ),
        )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    assert captured["url"] == (
        "https://gemini.test/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse"
    )
    assert streamed_text(chunks) == ["You spent ", "120.00."]
    assert final_response(chunks).content == "You spent 120.00."
    assert final_response(chunks).usage.total_tokens == 13
    assert final_response(chunks).finish_reason is FinishReason.STOP


async def test_gemini_streams_function_calls_with_synthetic_ids() -> None:
    def responder(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse_body(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "get_budget_status",
                                            "args": {"month": "2026-04"},
                                        }
                                    }
                                ]
                            },
                            "finishReason": "STOP",
                        }
                    ]
                }
            ),
        )

    chunks = [chunk async for chunk in build_provider(responder).stream(ChatRequest(messages=[]))]

    response = final_response(chunks)
    assert response.tool_calls[0].id
    assert response.tool_calls[0].name == "get_budget_status"
    assert response.tool_calls[0].arguments == {"month": "2026-04"}
    assert response.finish_reason is FinishReason.TOOL_CALLS
