"""create approval requests

Revision ID: 0002_create_approval_requests
Revises: 0001_create_conversations
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_approval_requests"
down_revision: str | None = "0001_create_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("arguments_hash", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("consequences_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        op.f("ix_approval_requests_owner_id"), "approval_requests", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_approval_requests_conversation_id"),
        "approval_requests",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_owner_status",
        "approval_requests",
        ["owner_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_requests_owner_status", table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_conversation_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_owner_id"), table_name="approval_requests")
    op.drop_table("approval_requests")
