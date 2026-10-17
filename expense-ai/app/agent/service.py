"""Assistant turn orchestration and event streaming.

``ChatService`` resolves (or creates) the owner's conversation, runs the bounded
graph, and turns graph progress into typed events. Persistence happens inside the
graph's final node, so a turn that fails before completion stores nothing rather
than a half-written or invented answer.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.errors import GraphRecursionError

from app.agent.events import StreamEvent, message_complete, message_start, status, token
from app.agent.events import error as error_event
from app.agent.graph import CompiledAgentGraph
from app.agent.policies import conversation_title
from app.agent.state import AgentContext, AgentState
from app.conversations.repository import ConversationRecord, ConversationRepository
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.identity.user_context import UserContext

logger = logging.getLogger(__name__)

_NODE_STAGES = {
    "classify_intent": "classifying",
    "plan": "planning",
    "validate_arguments": "validating",
    "authorize_tool": "authorizing",
    "execute_tool": "retrieving",
    "verify_result": "verifying",
    "compose_answer": "composing",
}


class ChatService:
    def __init__(
        self,
        *,
        graph: CompiledAgentGraph,
        repository: ConversationRepository,
        settings: Settings,
    ) -> None:
        self._graph = graph
        self._repository = repository
        self._settings = settings

    async def resolve_conversation(
        self,
        context: UserContext,
        *,
        conversation_id: str | None,
        message: str,
    ) -> ConversationRecord:
        """Return the caller's conversation, creating one for a first message.

        A conversation id that belongs to another user is reported as missing, so
        ids cannot be probed.
        """
        owner_id = context.user.user_id
        if conversation_id is None:
            title = conversation_title(message, max_length=self._settings.conversation_title_max_length)
            return await self._repository.create(owner_id=owner_id, title=title)

        conversation = await self._repository.get_for_owner(owner_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        return conversation

    async def stream_turn(
        self,
        context: UserContext,
        *,
        conversation: ConversationRecord,
        message: str,
    ) -> AsyncIterator[StreamEvent]:
        yield message_start(conversation_id=conversation.id)

        agent_context = AgentContext(
            user_context=context,
            conversation_id=conversation.id,
            repository=self._repository,
        )
        final: dict[str, Any] = {}

        try:
            async for update in self._graph.astream(
                AgentState(user_message=message),
                context=agent_context,
                stream_mode="updates",
                config={"recursion_limit": self._settings.agent_recursion_limit},
            ):
                for node, partial in update.items():
                    if isinstance(partial, dict):
                        final.update(partial)
                    event = _progress_event(node, partial)
                    if event is not None:
                        yield event
        except GraphRecursionError:
            logger.warning("event=agent_recursion_limit")
            yield error_event(
                code="iteration_limit",
                message="That question needed more steps than allowed. Please try a narrower question.",
                correlation_id=context.correlation_id,
            )
            return
        except AppError as exception:
            yield error_event(
                code=exception.code,
                message=exception.message,
                correlation_id=context.correlation_id,
            )
            return
        except Exception:
            logger.exception("event=agent_unhandled_failure")
            yield error_event(
                code="internal_error",
                message="An unexpected error occurred.",
                correlation_id=context.correlation_id,
            )
            return

        answer = final.get("answer")
        if not answer:
            yield error_event(
                code="no_answer",
                message="The assistant could not produce an answer.",
                correlation_id=context.correlation_id,
            )
            return

        yield token(text=answer)
        yield message_complete(
            conversation_id=conversation.id,
            message_id=_as_message_id(final.get("answer_message_id")),
            content=answer,
            termination=str(final.get("termination", "answered")),
            tool_calls=[str(name) for name in final.get("tool_names", [])],
        )


def _progress_event(node: str, partial: object) -> StreamEvent | None:
    stage = _NODE_STAGES.get(node)
    if stage is None:
        return None
    if stage == "retrieving" and isinstance(partial, dict):
        names = partial.get("tool_names")
        if isinstance(names, list) and names:
            return status(stage=stage, tool=str(names[-1]))
    return status(stage=stage)


def _as_message_id(value: object) -> int | None:
    return value if isinstance(value, int) else None
