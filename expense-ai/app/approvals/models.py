"""SQLAlchemy model for durable write approvals.

An approval is the only thing that authorises a write. It records the action, the
literal arguments, and a hash binding all of them to one owner, so a row that is
altered between proposal and execution cannot be executed. The table lives in the
AI service's own database; the financial schema remains Spring Boot's.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.conversations.models import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # The resource the action targets, when it has one (the budget month). Bound
    # into the hash so an approval cannot drift onto a different resource.
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    consequences_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_approval_requests_owner_status", "owner_id", "status"),)
