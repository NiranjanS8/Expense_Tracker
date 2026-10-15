"""Anthropic (Claude) Messages API adapter.

Differences from the OpenAI shape that this adapter absorbs:

* the system prompt is a top-level ``system`` field, not a message;
* assistant tool calls are ``tool_use`` content blocks;
* tool results are ``tool_result`` blocks inside a user message;
* usage is reported as ``input_tokens`` / ``output_tokens``.
"""

from __future__ import annotations

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

_ANTHROPIC_VERSION = "2023-06-01"

_STOP_REASONS = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
    "tool_use": FinishReason.TOOL_CALLS,
}


class AnthropicProvider(HttpModelProvider):
    name: ClassVar[str] = "anthropic"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        headers = {
            "x-api-key": require_api_key(self._config),
            "anthropic-version": _ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        system_prompt, messages = _encode_messages(request.messages)

        payload: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": request.max_output_tokens or 1024,
            "messages": messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.tools:
            payload["tools"] = [_encode_tool(tool) for tool in request.tools]
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        body = await self._post_json("/messages", payload=payload, headers=headers)
        return _decode_response(body)


def _encode_messages(messages: list[ChatMessage]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    encoded: list[dict[str, Any]] = []

    for message in messages:
        if message.role is Role.SYSTEM:
            if message.content:
                system_parts.append(message.content)
            continue

        if message.role is Role.TOOL:
            encoded.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id or "",
                            "content": message.content or "",
                        }
                    ],
                }
            )
            continue

        if message.role is Role.ASSISTANT and message.tool_calls:
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            blocks.extend(
                {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                for call in message.tool_calls
            )
            encoded.append({"role": "assistant", "content": blocks})
            continue

        encoded.append({"role": message.role.value, "content": message.content or ""})

    return "\n\n".join(system_parts), encoded


def _encode_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


def _decode_response(body: dict[str, Any]) -> ChatResponse:
    blocks = body.get("content") or []

    text_parts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
    tool_calls = [
        ToolCall(
            id=block.get("id", f"tool_{index}"),
            name=block.get("name", ""),
            arguments=block.get("input") if isinstance(block.get("input"), dict) else {},
        )
        for index, block in enumerate(blocks)
        if block.get("type") == "tool_use"
    ]

    usage = body.get("usage") or {}
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)

    return ChatResponse(
        provider="anthropic",
        model=body.get("model", ""),
        content="".join(text_parts) or None,
        tool_calls=tool_calls,
        finish_reason=_STOP_REASONS.get(body.get("stop_reason") or "", FinishReason.UNKNOWN),
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
