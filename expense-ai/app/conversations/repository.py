"""Owner-scoped repository for conversations and messages.

Every read and write filters on ``owner_id``; a conversation id belonging to
another user is indistinguishable from one that does not exist. Callers therefore
map "not found" onto ``404`` rather than ``403`` and cannot probe for other users'
conversations by guessing ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import selectinload

from app.conversations.database import Database
from app.conversations.models import Conversation, Message

USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"


@dataclass(frozen=True)
class ConversationRecord:
    id: str
    owner_id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MessageRecord:
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: datetime


class ConversationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(self, *, owner_id: int, title: str) -> ConversationRecord:
        now = datetime.now(UTC)
        conversation = Conversation(
            id=str(uuid4()),
            owner_id=owner_id,
            title=title,
            status="active",
            created_at=now,
            updated_at=now,
        )
        async with self._database.session_scope() as session:
            session.add(conversation)
            await session.commit()
        return _to_conversation(conversation)

    async def list_for_owner(self, owner_id: int, *, limit: int, offset: int = 0) -> list[ConversationRecord]:
        statement = (
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        async with self._database.session_scope() as session:
            conversations = (await session.scalars(statement)).all()
        return [_to_conversation(conversation) for conversation in conversations]

    async def get_for_owner(self, owner_id: int, conversation_id: str) -> ConversationRecord | None:
        conversation = await self._load(owner_id, conversation_id)
        return None if conversation is None else _to_conversation(conversation)

    async def get_messages(
        self, owner_id: int, conversation_id: str, *, limit: int
    ) -> list[MessageRecord] | None:
        """Oldest-first page of a conversation's messages, or ``None`` if not owned."""
        if await self._load(owner_id, conversation_id) is None:
            return None

        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
            .limit(limit)
        )
        async with self._database.session_scope() as session:
            messages = (await session.scalars(statement)).all()
        return [_to_message(message) for message in messages]

    async def recent_messages(
        self, owner_id: int, conversation_id: str, *, limit: int
    ) -> list[MessageRecord] | None:
        """The most recent ``limit`` messages, returned oldest-first for the model."""
        if await self._load(owner_id, conversation_id) is None:
            return None

        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        async with self._database.session_scope() as session:
            newest_first = (await session.scalars(statement)).all()
        return [_to_message(message) for message in reversed(newest_first)]

    async def append_message(
        self,
        owner_id: int,
        conversation_id: str,
        *,
        role: str,
        content: str,
    ) -> MessageRecord | None:
        if await self._load(owner_id, conversation_id) is None:
            return None

        now = datetime.now(UTC)
        message = Message(conversation_id=conversation_id, role=role, content=content, created_at=now)
        async with self._database.session_scope() as session:
            session.add(message)
            await session.execute(
                update(Conversation)
                .where(Conversation.id == conversation_id, Conversation.owner_id == owner_id)
                .values(updated_at=now)
            )
            await session.commit()
            await session.refresh(message)
        return _to_message(message)

    async def count_messages(self, owner_id: int, conversation_id: str) -> int | None:
        if await self._load(owner_id, conversation_id) is None:
            return None

        statement = (
            select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
        )
        async with self._database.session_scope() as session:
            return int(await session.scalar(statement) or 0)

    async def delete(self, owner_id: int, conversation_id: str) -> bool:
        statement = (
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.owner_id == owner_id)
            .options(selectinload(Conversation.messages))
        )
        async with self._database.session_scope() as session:
            conversation = (await session.scalars(statement)).one_or_none()
            if conversation is None:
                return False
            await session.delete(conversation)
            await session.commit()
        return True

    async def delete_all_for_owner(self, owner_id: int) -> int:
        """Retention helper: remove every conversation a user owns, with its messages."""
        async with self._database.session_scope() as session:
            conversation_ids = list(
                (
                    await session.scalars(select(Conversation.id).where(Conversation.owner_id == owner_id))
                ).all()
            )
            if not conversation_ids:
                return 0
            # Explicit message deletion keeps the cascade correct on dialects that
            # do not enforce ON DELETE CASCADE by default (notably SQLite).
            await session.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
            await session.execute(delete(Conversation).where(Conversation.owner_id == owner_id))
            await session.commit()
        return len(conversation_ids)

    async def _load(self, owner_id: int, conversation_id: str) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.owner_id == owner_id,
        )
        async with self._database.session_scope() as session:
            return (await session.scalars(statement)).one_or_none()


def _to_conversation(conversation: Conversation) -> ConversationRecord:
    return ConversationRecord(
        id=conversation.id,
        owner_id=conversation.owner_id,
        title=conversation.title,
        status=conversation.status,
        created_at=_as_utc(conversation.created_at),
        updated_at=_as_utc(conversation.updated_at),
    )


def _to_message(message: Message) -> MessageRecord:
    return MessageRecord(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        created_at=_as_utc(message.created_at),
    )


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive timestamps; every value is written as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
