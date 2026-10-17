"""Google Gemini (Generative Language API) adapter.

Differences this adapter absorbs:

* contents use ``parts`` with ``text`` or ``functionCall`` entries;
* the system prompt is ``systemInstruction``;
* tools are ``functionDeclarations`` and use ``parameters`` (OpenAPI schema);
* Gemini returns no tool-call IDs, so stable synthetic IDs are generated;
* the API key is sent as ``x-goog-api-key`` rather than a query parameter so it
  can never appear in a logged URL.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from app.integrations.model_provider.base import HttpModelProvider, require_api_key
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
    "STOP": FinishReason.STOP,
    "MAX_TOKENS": FinishReason.LENGTH,
    "SAFETY": FinishReason.CONTENT_FILTER,
    "RECITATION": FinishReason.CONTENT_FILTER,
}


class GeminiProvider(HttpModelProvider):
    name: ClassVar[str] = "gemini"

    async def complete(self, request: ChatRequest) -> ChatResponse:
        body = await self._post_json(
            f"/models/{self._config.model}:generateContent",
            payload=self._encode_request(request),
            headers=self._headers(),
        )
        return _decode_response(body)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ModelStreamChunk]:
        text_parts: list[str] = []
        function_calls: list[dict[str, Any]] = []
        usage = TokenUsage()
        model = self._config.model
        finish_reason = FinishReason.UNKNOWN

        async for event in self._stream_json(
            f"/models/{self._config.model}:streamGenerateContent?alt=sse",
            payload=self._encode_request(request),
            headers=self._headers(),
        ):
            if event.get("modelVersion"):
                model = str(event["modelVersion"])
            if event.get("usageMetadata"):
                usage = _decode_usage(event["usageMetadata"])

            for candidate in event.get("candidates") or []:
                for part in (candidate.get("content") or {}).get("parts") or []:
                    text = part.get("text")
                    if text:
                        text_parts.append(text)
                        yield TextDelta(text=text)
                    if "functionCall" in part:
                        function_calls.append(part["functionCall"] or {})
                if candidate.get("finishReason"):
                    finish_reason = _FINISH_REASONS.get(candidate["finishReason"], FinishReason.UNKNOWN)

        tool_calls = [
            ToolCall(
                id=f"gemini_call_{index}",
                name=str(call.get("name", "")),
                arguments=call.get("args") if isinstance(call.get("args"), dict) else {},
            )
            for index, call in enumerate(function_calls)
        ]
        if tool_calls:
            finish_reason = FinishReason.TOOL_CALLS

        yield Completion(
            response=ChatResponse(
                provider=self.name,
                model=model,
                content="".join(text_parts) or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": require_api_key(self._config),
            "Content-Type": "application/json",
        }

    def _encode_request(self, request: ChatRequest) -> dict[str, Any]:
        system_prompt, contents = _encode_contents(request.messages)
        payload: dict[str, Any] = {"contents": contents}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if request.tools:
            payload["tools"] = [{"functionDeclarations": [_encode_tool(tool) for tool in request.tools]}]

        generation_config: dict[str, Any] = {"maxOutputTokens": request.max_output_tokens or 1024}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        payload["generationConfig"] = generation_config

        return payload


def _encode_contents(messages: list[ChatMessage]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []

    for message in messages:
        if message.role is Role.SYSTEM:
            if message.content:
                system_parts.append(message.content)
            continue

        if message.role is Role.TOOL:
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": message.name or "tool",
                                "response": {"content": message.content or ""},
                            }
                        }
                    ],
                }
            )
            continue

        if message.role is Role.ASSISTANT and message.tool_calls:
            parts: list[dict[str, Any]] = []
            if message.content:
                parts.append({"text": message.content})
            parts.extend(
                {"functionCall": {"name": call.name, "args": call.arguments}} for call in message.tool_calls
            )
            contents.append({"role": "model", "parts": parts})
            continue

        role = "model" if message.role is Role.ASSISTANT else "user"
        contents.append({"role": role, "parts": [{"text": message.content or ""}]})

    return "\n\n".join(system_parts), contents


def _encode_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
    }


def _decode_response(body: dict[str, Any]) -> ChatResponse:
    candidates = body.get("candidates") or []
    candidate = candidates[0] if candidates else {}
    parts = candidate.get("content", {}).get("parts") or []

    text = "".join(part.get("text", "") for part in parts if "text" in part)

    tool_calls = [
        ToolCall(
            id=f"gemini_call_{index}",
            name=part["functionCall"].get("name", ""),
            arguments=part["functionCall"].get("args")
            if isinstance(part["functionCall"].get("args"), dict)
            else {},
        )
        for index, part in enumerate(parts)
        if "functionCall" in part
    ]

    if tool_calls:
        finish_reason = FinishReason.TOOL_CALLS
    else:
        finish_reason = _FINISH_REASONS.get(candidate.get("finishReason") or "", FinishReason.UNKNOWN)

    usage = _decode_usage(body.get("usageMetadata") or {})

    return ChatResponse(
        provider="gemini",
        model=body.get("modelVersion", ""),
        content=text or None,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
    )


def _decode_usage(metadata: dict[str, Any]) -> TokenUsage:
    prompt_tokens = metadata.get("promptTokenCount", 0)
    completion_tokens = metadata.get("candidatesTokenCount", 0)
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=metadata.get("totalTokenCount", prompt_tokens + completion_tokens),
    )
