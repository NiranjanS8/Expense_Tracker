"""OpenAI Chat Completions adapter.

OpenAI, Mistral and DeepSeek all expose an OpenAI-compatible
``/chat/completions`` endpoint, so they share this mapping and differ only in
base URL, model and credentials.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from app.integrations.model_provider.base import HttpModelProvider, require_api_key
from app.integrations.model_provider.types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    FinishReason,
    Role,
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

    async def complete(self, request: ChatRequest) -> ChatResponse:
        headers = {
            "Authorization": f"Bearer {require_api_key(self._config)}",
            "Content-Type": "application/json",
        }
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

        body = await self._post_json("/chat/completions", payload=payload, headers=headers)
        return _decode_response(body)


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


def _decode_response(body: dict[str, Any]) -> ChatResponse:
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
            arguments=_decode_arguments(call.get("function", {}).get("arguments")),
        )
        for index, call in enumerate(message.get("tool_calls") or [])
    ]

    usage = body.get("usage") or {}
    return ChatResponse(
        provider="openai-compatible",
        model=body.get("model", ""),
        content=message.get("content"),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        ),
    )


def _decode_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        decoded = json.loads(raw)
    except ValueError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


class OpenAiProvider(OpenAiCompatibleProvider):
    name: ClassVar[str] = "openai"


class MistralProvider(OpenAiCompatibleProvider):
    name: ClassVar[str] = "mistral"


class DeepSeekProvider(OpenAiCompatibleProvider):
    name: ClassVar[str] = "deepseek"
