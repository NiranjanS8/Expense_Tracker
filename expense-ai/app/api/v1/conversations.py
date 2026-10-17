"""Conversation read and delete endpoints.

Everything here is owner-scoped through the repository: a conversation id that
belongs to another user is reported as ``404``, never ``403``, so ids cannot be
enumerated. Message content is returned to its owner only.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.v1.schemas import ConversationDetail, ConversationSummary, MessageView
from app.conversations.repository import ConversationRecord, ConversationRepository
from app.core.errors import NotFoundError
from app.identity.user_context import UserContext, get_user_context

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_repository(request: Request) -> ConversationRepository:
    return cast(ConversationRepository, request.app.state.conversation_repository)


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> list[ConversationSummary]:
    repository = get_repository(request)
    records = await repository.list_for_owner(
        context.user.user_id,
        limit=request.app.state.settings.conversation_list_limit,
    )
    return [_summarise(record) for record in records]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> ConversationDetail:
    repository = get_repository(request)
    owner_id = context.user.user_id

    conversation = await repository.get_for_owner(owner_id, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation not found.")

    messages = (
        await repository.get_messages(
            owner_id,
            conversation_id,
            limit=request.app.state.settings.conversation_message_limit,
        )
        or []
    )
    summary = _summarise(conversation)
    return ConversationDetail(
        id=summary.id,
        title=summary.title,
        status=summary.status,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        messages=[
            MessageView(
                id=message.id, role=message.role, content=message.content, created_at=message.created_at
            )
            for message in messages
        ],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> Response:
    deleted = await get_repository(request).delete(context.user.user_id, conversation_id)
    if not deleted:
        raise NotFoundError("Conversation not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _summarise(record: ConversationRecord) -> ConversationSummary:
    return ConversationSummary(
        id=record.id,
        title=record.title,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
