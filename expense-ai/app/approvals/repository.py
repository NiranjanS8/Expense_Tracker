"""Owner-scoped persistence for write approvals.

Every read and write filters on ``owner_id``. State transitions that authorise a
write are conditional ``UPDATE``s, so two concurrent approvals of the same request
cannot both execute: exactly one claim succeeds and the other sees a conflict.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from app.approvals.models import ApprovalRequest
from app.conversations.database import Database

PENDING = "pending"
EXECUTING = "executing"
EXECUTED = "executed"
FAILED = "failed"
UNKNOWN = "unknown"
CANCELLED = "cancelled"
EXPIRED = "expired"

_TERMINAL = frozenset({EXECUTED, FAILED, UNKNOWN, CANCELLED, EXPIRED})


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    owner_id: int
    conversation_id: str | None
    action: str
    resource_id: str | None
    arguments: dict[str, Any]
    arguments_hash: str
    summary: str
    details: list[dict[str, str]]
    consequences: list[str]
    status: str
    idempotency_key: str
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None
    outcome: dict[str, Any] | None

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL


class ApprovalRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(
        self,
        *,
        owner_id: int,
        conversation_id: str | None,
        action: str,
        resource_id: str | None,
        arguments: dict[str, Any],
        arguments_hash: str,
        summary: str,
        details: list[dict[str, str]],
        consequences: list[str],
        ttl_seconds: int,
        now: datetime,
    ) -> ApprovalRecord:
        approval = ApprovalRequest(
            id=str(uuid4()),
            owner_id=owner_id,
            conversation_id=conversation_id,
            action=action,
            resource_id=resource_id,
            arguments_json=json.dumps(arguments, sort_keys=True, separators=(",", ":")),
            arguments_hash=arguments_hash,
            summary=summary,
            details_json=json.dumps(details, sort_keys=True),
            consequences_json=json.dumps(list(consequences)),
            status=PENDING,
            idempotency_key=str(uuid4()),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        async with self._database.session_scope() as session:
            session.add(approval)
            await session.commit()
        return _to_record(approval)

    async def list_pending_for_conversation(
        self, owner_id: int, conversation_id: str, *, now: datetime
    ) -> list[ApprovalRecord]:
        statement = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.owner_id == owner_id,
                ApprovalRequest.conversation_id == conversation_id,
                ApprovalRequest.status == PENDING,
                ApprovalRequest.expires_at > now,
            )
            .order_by(ApprovalRequest.created_at.asc())
        )
        async with self._database.session_scope() as session:
            approvals = (await session.scalars(statement)).all()
        return [_to_record(approval) for approval in approvals]

    async def get_for_owner(self, owner_id: int, approval_id: str) -> ApprovalRecord | None:
        statement = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.owner_id == owner_id,
        )
        async with self._database.session_scope() as session:
            approval = (await session.scalars(statement)).one_or_none()
        return None if approval is None else _to_record(approval)

    async def claim(self, owner_id: int, approval_id: str, *, now: datetime) -> bool:
        """Atomically move one pending, unexpired approval into ``executing``."""
        statement = (
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.owner_id == owner_id,
                ApprovalRequest.status == PENDING,
                ApprovalRequest.expires_at > now,
            )
            .values(status=EXECUTING, started_at=now)
        )
        async with self._database.session_scope() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()
            return result.rowcount == 1

    async def resolve(
        self,
        owner_id: int,
        approval_id: str,
        *,
        status: str,
        outcome: dict[str, Any],
        now: datetime,
    ) -> None:
        statement = (
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.owner_id == owner_id,
                ApprovalRequest.status == EXECUTING,
            )
            .values(
                status=status,
                outcome_json=json.dumps(outcome, sort_keys=True),
                resolved_at=now,
            )
        )
        async with self._database.session_scope() as session:
            await session.execute(statement)
            await session.commit()

    async def cancel(self, owner_id: int, approval_id: str, *, now: datetime) -> bool:
        statement = (
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.owner_id == owner_id,
                ApprovalRequest.status == PENDING,
                ApprovalRequest.expires_at > now,
            )
            .values(status=CANCELLED, resolved_at=now, outcome_json='{"message": "Cancelled."}')
        )
        async with self._database.session_scope() as session:
            result = cast(CursorResult[Any], await session.execute(statement))
            await session.commit()
            return result.rowcount == 1

    async def mark_expired(self, owner_id: int, approval_id: str, *, now: datetime) -> None:
        statement = (
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.owner_id == owner_id,
                ApprovalRequest.status == PENDING,
            )
            .values(status=EXPIRED, resolved_at=now, outcome_json='{"message": "Expired."}')
        )
        async with self._database.session_scope() as session:
            await session.execute(statement)
            await session.commit()


def _to_record(approval: ApprovalRequest) -> ApprovalRecord:
    return ApprovalRecord(
        id=approval.id,
        owner_id=approval.owner_id,
        conversation_id=approval.conversation_id,
        action=approval.action,
        resource_id=approval.resource_id,
        arguments=json.loads(approval.arguments_json),
        arguments_hash=approval.arguments_hash,
        summary=approval.summary,
        details=json.loads(approval.details_json),
        consequences=json.loads(approval.consequences_json),
        status=approval.status,
        idempotency_key=approval.idempotency_key,
        created_at=_as_utc(approval.created_at),
        expires_at=_as_utc(approval.expires_at),
        resolved_at=None if approval.resolved_at is None else _as_utc(approval.resolved_at),
        outcome=None if approval.outcome_json is None else json.loads(approval.outcome_json),
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
