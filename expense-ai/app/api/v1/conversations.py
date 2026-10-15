"""Conversation read/delete endpoints.

Conversation persistence is owner-scoped and arrives in Phase 3. These routes
exist in Phase 1 so the authentication boundary is exercised end to end; they
return ``501`` rather than pretending to have data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.errors import NotImplementedYetError
from app.identity.user_context import UserContext, get_user_context

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(context: UserContext = Depends(get_user_context)) -> None:
    raise NotImplementedYetError("Conversation history is not implemented yet.")


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    context: UserContext = Depends(get_user_context),
) -> None:
    raise NotImplementedYetError("Conversation history is not implemented yet.")


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    context: UserContext = Depends(get_user_context),
) -> None:
    raise NotImplementedYetError("Conversation deletion is not implemented yet.")
