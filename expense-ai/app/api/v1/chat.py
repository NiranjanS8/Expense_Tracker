"""Chat submission endpoint.

Phase 1 establishes the authentication boundary and request contract only. The
bounded LangGraph workflow that answers questions is implemented in Phase 3, so
this route deliberately returns ``501`` rather than fabricating a response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.errors import NotImplementedYetError
from app.identity.user_context import UserContext, get_user_context

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)


@router.post("")
async def submit_message(
    body: ChatRequest,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> None:
    request.app.state.chat_limiter.check(f"chat:user:{context.user.user_id}")
    raise NotImplementedYetError("Chat is not implemented yet. It arrives in Phase 3.")
