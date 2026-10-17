"""Provider-agnostic model contracts.

The rest of the service speaks only in these types. Provider-specific wire
formats (OpenAI ``tools``, Anthropic ``tool_use`` blocks, Gemini
``functionDeclarations``) are confined to the adapters in this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    UNKNOWN = "unknown"


class ToolSpec(BaseModel):
    """An allowlisted tool the model may request. ``parameters`` is JSON Schema."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    tools: list[ToolSpec] = Field(default_factory=list)
    temperature: float | None = None
    max_output_tokens: int | None = None


class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    usage: TokenUsage = Field(default_factory=TokenUsage)


@dataclass(frozen=True, slots=True)
class TextDelta:
    """A content increment a caller may forward before the completion is assembled."""

    text: str


@dataclass(frozen=True, slots=True)
class Completion:
    """The assembled completion. Always the final item of a stream."""

    response: ChatResponse


# A provider yields zero or more deltas, then exactly one completion.
ModelStreamChunk = TextDelta | Completion
