"""Node implementations for the bounded assistant workflow.

Each node performs exactly one step and returns a partial state update. Financial
data enters the state only as the serialized result of an allowlisted tool; the
model never sees the bearer token, and a data question that produced no tool
result is answered with a deterministic refusal rather than a free-form guess.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from langgraph.runtime import Runtime

from app.agent.policies import DATA_INTENT, classify_intent
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentContext, AgentState
from app.conversations.repository import ASSISTANT_ROLE, USER_ROLE
from app.core.config import Settings
from app.core.errors import AppError
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.integrations.model_provider import (
    ChatMessage,
    ChatRequest,
    ModelProvider,
    ProviderError,
    Role,
    ToolSpec,
)
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_MODEL_UNAVAILABLE = (
    "The assistant is temporarily unavailable, so I couldn't answer that. Please try again shortly."
)
_TOOL_FAILURE = (
    "I couldn't retrieve the data needed to answer that, and I won't guess at the figures. "
    "Please try again shortly."
)
_NO_DATA = (
    "I wasn't able to look that up in your Expense Tracker data, so I can't answer it reliably. "
    "Try rephrasing with a period such as \u201cthis month\u201d."
)
_NO_ANSWER = "I don't have an answer for that. Please try asking in a different way."


class AgentNodes:
    """Builds the node callables once; per-request identity arrives via runtime context."""

    def __init__(
        self,
        *,
        provider: Callable[[], ModelProvider | None],
        client: Callable[[], ExpenseTrackerClient],
        registry: ToolRegistry,
        settings: Settings,
    ) -> None:
        self._provider = provider
        self._client = client
        self._registry = registry
        self._settings = settings
        self._tool_specs = tuple(
            ToolSpec(
                name=definition.name,
                description=definition.description,
                parameters=definition.arguments_schema(),
            )
            for definition in registry.definitions
        )

    async def load_context(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        context = runtime.context
        records = (
            await context.repository.recent_messages(
                context.user_context.user.user_id,
                context.conversation_id,
                limit=self._settings.agent_history_messages,
            )
            or []
        )
        history = [_to_chat_message(record.role, record.content) for record in records]
        working = [
            ChatMessage(role=Role.SYSTEM, content=SYSTEM_PROMPT),
            *history,
            ChatMessage(role=Role.USER, content=state["user_message"]),
        ]
        return {
            "history": history,
            "working": working,
            "tool_call": None,
            "tool_calls_made": 0,
            "tool_names": [],
        }

    async def classify_intent(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        return {"intent": classify_intent(state["user_message"])}

    async def plan(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        provider = self._provider()
        if provider is None:
            return _model_failure("model_unavailable")

        try:
            response = await provider.complete(
                self._chat_request(state["working"], tools=list(self._tool_specs))
            )
        except ProviderError:
            logger.warning("event=agent_model_error node=plan")
            return _model_failure("model_error")

        working = list(state["working"])
        if response.tool_calls:
            call = response.tool_calls[0]
            working.append(
                ChatMessage(
                    role=Role.ASSISTANT, content=response.content, tool_calls=list(response.tool_calls)
                )
            )
            return {"working": working, "tool_call": call}

        content = (response.content or "").strip()
        working.append(ChatMessage(role=Role.ASSISTANT, content=content))
        if content:
            return {"working": working, "tool_call": None, "answer": content, "termination": "answered"}
        return {"working": working, "tool_call": None, "answer": None}

    async def validate_arguments(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        call = state.get("tool_call")
        if call is None:
            return {"tool_error": "invalid_request", "error_code": "invalid_request"}
        try:
            self._registry.prepare(call.name, call.arguments)
        except AppError:
            return {"tool_error": "invalid_arguments", "error_code": "invalid_arguments"}
        return {"tool_error": None}

    async def authorize_tool(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        call = state.get("tool_call")
        if call is None or not self._registry.is_allowed(call.name):
            return {"tool_error": "tool_not_allowed", "error_code": "tool_not_allowed"}
        if state.get("tool_calls_made", 0) >= self._settings.agent_max_tool_calls:
            return {"tool_error": "tool_budget_exhausted", "error_code": "tool_budget_exhausted"}
        return {"error_code": None}

    async def execute_tool(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        call = state["tool_call"]
        if call is None:  # pragma: no cover - guarded by routing
            return {"tool_error": "invalid_request", "error_code": "invalid_request"}

        context = runtime.context
        working = list(state["working"])
        tool_calls_made = state.get("tool_calls_made", 0) + 1
        tool_names = [*state.get("tool_names", []), call.name]

        try:
            prepared = self._registry.prepare(call.name, call.arguments)
            result = await self._registry.run(prepared, client=self._client(), context=context.user_context)
        except AppError as exception:
            working.append(_tool_message(call.id, call.name, {"error": exception.code}))
            return {
                "working": working,
                "tool_error": exception.code,
                "tool_result_json": None,
                "tool_calls_made": tool_calls_made,
                "tool_names": tool_names,
                "termination": "tool_error",
            }

        payload = result.model_dump_json()
        working.append(_tool_message(call.id, call.name, payload))
        return {
            "working": working,
            "tool_result_json": payload,
            "tool_error": None,
            "tool_calls_made": tool_calls_made,
            "tool_names": tool_names,
        }

    async def verify_result(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        if state.get("tool_error"):
            return {"termination": "tool_error", "error_code": state.get("tool_error")}
        if not state.get("tool_result_json"):
            return {"tool_error": "empty_result", "error_code": "empty_result", "termination": "tool_error"}
        return {"termination": "tool_ok"}

    async def compose_answer(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        error_code = state.get("error_code")

        # A data question with no retrieved figures is never answered freely, even
        # if the model offered prose: that prose could only be invented numbers.
        ungounded_data_question = (
            state.get("intent") == DATA_INTENT
            and not state.get("tool_result_json")
            and not state.get("tool_error")
        )
        if ungounded_data_question:
            if error_code in ("model_error", "model_unavailable"):
                return {"answer": _MODEL_UNAVAILABLE, "termination": "model_error"}
            return {"answer": _NO_DATA, "termination": "no_data", "error_code": "no_tool_data"}

        if state.get("answer"):
            return {"termination": state.get("termination", "answered")}
        if error_code in ("model_error", "model_unavailable"):
            return {"answer": _MODEL_UNAVAILABLE, "termination": "model_error"}
        if state.get("tool_error"):
            return {"answer": _TOOL_FAILURE, "termination": "tool_error"}

        provider = self._provider()
        if provider is None:
            return {
                "answer": _MODEL_UNAVAILABLE,
                "termination": "model_error",
                "error_code": "model_unavailable",
            }

        try:
            response = await provider.complete(self._chat_request(state["working"], tools=[]))
        except ProviderError:
            logger.warning("event=agent_model_error node=compose_answer")
            return {"answer": _MODEL_UNAVAILABLE, "termination": "model_error", "error_code": "model_error"}

        content = (response.content or "").strip()
        if not content:
            return {"answer": _NO_ANSWER, "termination": "no_answer", "error_code": "empty_model_response"}
        return {"answer": content, "termination": "answered"}

    async def persist_and_trace(self, state: AgentState, runtime: Runtime[AgentContext]) -> AgentState:
        context = runtime.context
        owner_id = context.user_context.user.user_id
        answer = (state.get("answer") or "").strip() or _NO_ANSWER

        await context.repository.append_message(
            owner_id, context.conversation_id, role=USER_ROLE, content=state["user_message"]
        )
        stored = await context.repository.append_message(
            owner_id, context.conversation_id, role=ASSISTANT_ROLE, content=answer
        )

        # Trace metadata only: no amounts, descriptions or category names.
        logger.info(
            "event=agent_turn user_id=%s intent=%s termination=%s tool_calls=%s",
            owner_id,
            state.get("intent"),
            state.get("termination", "answered"),
            state.get("tool_calls_made", 0),
        )
        return {
            "answer": answer,
            "answer_message_id": stored.id if stored is not None else None,
            "termination": state.get("termination", "answered"),
        }

    def _chat_request(self, messages: list[ChatMessage], *, tools: list[ToolSpec]) -> ChatRequest:
        return ChatRequest(
            messages=messages,
            tools=tools,
            temperature=self._settings.llm_temperature,
            max_output_tokens=self._settings.llm_max_output_tokens,
        )


def _model_failure(code: str) -> AgentState:
    return {"tool_call": None, "answer": None, "error_code": code, "termination": "model_error"}


def _tool_message(tool_call_id: str, name: str, payload: str | dict[str, str]) -> ChatMessage:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return ChatMessage(role=Role.TOOL, content=content, tool_call_id=tool_call_id, name=name)


def _to_chat_message(role: str, content: str) -> ChatMessage:
    return ChatMessage(role=Role.USER if role == USER_ROLE else Role.ASSISTANT, content=content)
