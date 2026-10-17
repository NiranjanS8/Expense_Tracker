"""Typed state for the bounded assistant workflow.

The state deliberately holds no credentials: the bearer token lives in
:class:`AgentContext`, which LangGraph passes to nodes as request-scoped runtime
context and which is never persisted, logged, or sent to the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from app.conversations.repository import ConversationRepository
from app.identity.user_context import UserContext
from app.integrations.model_provider import ChatMessage, ToolCall


class AgentState(TypedDict, total=False):
    """Everything one assistant turn carries between graph nodes."""

    user_message: str
    history: list[ChatMessage]
    working: list[ChatMessage]
    intent: str
    tool_call: ToolCall | None
    tool_calls_made: int
    tool_names: list[str]
    tool_result_json: str | None
    tool_error: str | None
    answer: str | None
    answer_message_id: int | None
    termination: str
    error_code: str | None


@dataclass(frozen=True)
class AgentContext:
    """Request-scoped dependencies and identity, never part of the model prompt."""

    user_context: UserContext
    conversation_id: str
    repository: ConversationRepository
