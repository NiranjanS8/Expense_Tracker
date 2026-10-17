"""Chat submission endpoint.

The turn is answered by the bounded LangGraph workflow and streamed back as typed
server-sent events. Authentication and conversation ownership are resolved before
streaming begins, so a ``401`` or ``404`` is a normal JSON response rather than an
event on the stream.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.events import ERROR, MESSAGE_COMPLETE
from app.agent.service import ChatService
from app.api.v1.streaming import SSE_HEADERS, SSE_MEDIA_TYPE, encode_sse
from app.identity.user_context import UserContext, get_user_context
from app.observability.metrics import metrics

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)


@router.post("")
async def submit_message(
    body: ChatRequest,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> StreamingResponse:
    request.app.state.chat_limiter.check(f"chat:user:{context.user.user_id}")

    service: ChatService = request.app.state.chat_service
    conversation = await service.resolve_conversation(
        context,
        conversation_id=body.conversation_id,
        message=body.message,
    )

    events = service.stream_turn(context, conversation=conversation, message=body.message)

    async def event_stream() -> AsyncIterator[str]:
        started = time.perf_counter()
        outcome = "incomplete"
        try:
            async for event in events:
                if event.event == MESSAGE_COMPLETE:
                    outcome = str(event.data.get("termination", "answered"))
                elif event.event == ERROR:
                    outcome = f"error:{event.data.get('code', 'unknown')}"
                yield encode_sse(event)
        except GeneratorExit:
            outcome = "cancelled"
            raise
        finally:
            metrics.record_chat_turn(
                outcome=outcome,
                duration_seconds=time.perf_counter() - started,
            )

    return StreamingResponse(event_stream(), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)
