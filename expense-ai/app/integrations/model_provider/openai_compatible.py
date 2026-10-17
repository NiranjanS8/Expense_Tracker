"""OpenAI Chat Completions adapter.

OpenAI, Mistral and DeepSeek all expose an OpenAI-compatible
``/chat/completions`` endpoint, so they share this mapping and differ only in
base URL, model and credentials.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from app.integrations.model_provider.base import (
    HttpModelProvider,
    accumulate_tool_call,
    assemble_tool_calls,
    decode_json_object,
    require_api_key,
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

_FINISH_REASONS = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "tool_calls": FinishReason.TOOL_CALLS,
    "content_filter": FinishReason.CONTENT_FILTER,
}


class OpenAiCompatibleProvider(HttpModelProvider):
    name: ClassVar[str] = "openai-compatible"

    # Whether the endpoint accepts OpenAI's ``stream_options.include_usage``.
    # Set only where it is known to be accepted: an unknown field fails the whole
    # request. Without it usage is still read from any chunk that carries it.
    requests_stream_usage: ClassVar[bool] = False

    async def complete(self, request: ChatRequest) -> ChatResponse:
        body = await self._post_json(
            "/chat/completions",
            payload=self._encode_request(request),
            headers=self._headers(),
        )
        return _decode_response(body, provider=self.name)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ModelStreamChunk]:
        payload = self._encode_request(request)
        payload["stream"] = True
        if self.requests_stream_usage:
            payload["stream_options"] = {"include_usage": True}

        text_parts: list[str] = []
        partial_calls: dict[int, dict[str, Any]] = {}
        usage = TokenUsage()
        model = self._config.model
        finish_reason = FinishReason.UNKNOWN

        async for event in self._stream_json("/chat/completions", payload=payload, headers=self._headers()):
            if event.get("model"):
                model = str(event["model"])
            if event.get("usage"):
                usage = _decode_usage(event["usage"])

            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                text = delta.get("content")
                if text:
                    text_parts.append(text)
                    yield TextDelta(text=text)
                for partial in delta.get("tool_calls") or []:
                    function = partial.get("function") or {}
                    accumulate_tool_call(
                        partial_calls,
                        index=partial.get("index"),
                        call_id=partial.get("id"),
                        name=function.get("name"),
                        arguments=function.get("arguments"),
                    )
                if choice.get("finish_reason"):
                    finish_reason = _FINISH_REASONS.get(choice["finish_reason"], FinishReason.UNKNOWN)

        yield Completion(
            response=ChatResponse(
                provider=self.name,
                model=model,
                content="".join(text_parts) or None,
                tool_calls=assemble_tool_calls(partial_calls, id_prefix="call_"),
                finish_reason=finish_reason,
                usage=usage,
            )
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {require_api_key(self._config)}",
            "Content-Type": "application/json",
        }

    def _encode_request(self, request: ChatRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [_encode_message(message) for message in request.messages],
        }

        if request.tools:
            payload["tools"] = [_encode_tool(tool) for tool in request.tools]

        temperature = request.temperature
        if temperature is not None:
            payload["temperature"] = temperature

        max_tokens = request.max_output_tokens
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        return payload


def _encode_message(message: ChatMessage) -> dict[str, Any]:
    encoded: dict[str, Any] = {"role": message.role.value}

    if message.role is Role.TOOL:
        encoded["content"] = message.content or ""
        if message.tool_call_id is not None:
            encoded["tool_call_id"] = message.tool_call_id
        return encoded

    encoded["content"] = message.content

    if message.role is Role.ASSISTANT and message.tool_calls:
        encoded["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]

    return encoded


def _encode_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _decode_response(body: dict[str, Any], *, provider: str) -> ChatResponse:
    choices = body.get("choices") or []
    if choices:
        choice = choices[0]
        message = choice.get("message", {})
        finish_reason = _FINISH_REASONS.get(choice.get("finish_reason", ""), FinishReason.UNKNOWN)
    else:
        message, finish_reason = {}, FinishReason.UNKNOWN

    tool_calls = [
        ToolCall(
            id=call.get("id", f"call_{index}"),
            name=call.get("function", {}).get("name", ""),
            arguments=decode_json_object(call.get("function", {}).get("arguments")),
        )
        for index, call in enumerate(message.get("tool_calls") or [])
    ]

    return ChatResponse(
        provider=provider,
        model=body.get("model", ""),
        content=message.get("content"),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=_decode_usage(body.get("usage") or {}),
    )


def _decode_usage(usage: dict[str, Any]) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )


class OpenAiProvider(OpenAiCompatibleProvider):
    name: ClassVar[str] = "openai"
    requests_stream_usage: ClassVar[bool] = True


class MistralProvider(OpenAiCompatibleProvider):
    name: ClassVar[str] = "mistral"


class DeepSeekProvider(OpenAiCompatibleProvider):
    name: ClassVar[str] = "deepseek"
    requests_stream_usage: ClassVar[bool] = True
