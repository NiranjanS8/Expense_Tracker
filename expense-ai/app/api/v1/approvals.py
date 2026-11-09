"""Explicit approval of a proposed write.

These endpoints are the only route by which the assistant's proposal can become a
change. They are closed unless confirmed writes are enabled, every lookup is
owner-scoped (another user's id is a ``404``, never a ``403``), and the approval
itself is single-use.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.schemas import ApprovalDetail, ApprovalView
from app.approvals.repository import ApprovalRecord
from app.approvals.service import ApprovalService
from app.core.errors import NotFoundError
from app.identity.user_context import UserContext, get_user_context

router = APIRouter(prefix="/approvals", tags=["approvals"])


def get_service(request: Request) -> ApprovalService:
    if not request.app.state.settings.write_operations_enabled:
        # With the feature off no approval can be created, so the surface does not
        # exist rather than advertising a capability that cannot be used.
        raise NotFoundError("Approval not found.")
    return cast(ApprovalService, request.app.state.approval_service)


@router.get("", response_model=list[ApprovalView])
async def list_pending_approvals(
    request: Request,
    conversation_id: str = Query(alias="conversationId", min_length=1, max_length=64),
    context: UserContext = Depends(get_user_context),
) -> list[ApprovalView]:
    """Still-actionable proposals for one conversation, so a reload keeps them."""
    records = await get_service(request).list_pending(
        owner_id=context.user.user_id,
        conversation_id=conversation_id,
    )
    return [_to_view(record) for record in records]


@router.get("/{approval_id}", response_model=ApprovalView)
async def get_approval(
    approval_id: str,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> ApprovalView:
    record = await get_service(request).get(
        owner_id=context.user.user_id,
        approval_id=approval_id,
    )
    return _to_view(record)


@router.post("/{approval_id}/approve", response_model=ApprovalView)
async def approve(
    approval_id: str,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> ApprovalView:
    request.app.state.approval_limiter.check(f"approval:user:{context.user.user_id}")
    record = await get_service(request).approve(
        owner_id=context.user.user_id,
        approval_id=approval_id,
        token=context.token,
        correlation_id=context.correlation_id,
    )
    return _to_view(record)


@router.post("/{approval_id}/cancel", response_model=ApprovalView)
async def cancel(
    approval_id: str,
    request: Request,
    context: UserContext = Depends(get_user_context),
) -> ApprovalView:
    request.app.state.approval_limiter.check(f"approval:user:{context.user.user_id}")
    record = await get_service(request).cancel(
        owner_id=context.user.user_id,
        approval_id=approval_id,
    )
    return _to_view(record)


def _to_view(record: ApprovalRecord) -> ApprovalView:
    outcome = record.outcome or {}
    message = outcome.get("message")
    return ApprovalView(
        id=record.id,
        action=record.action,
        status=record.status,
        summary=record.summary,
        details=[ApprovalDetail(label=item["label"], value=item["value"]) for item in record.details],
        consequences=record.consequences,
        outcome=message if isinstance(message, str) else None,
        created_at=record.created_at,
        expires_at=record.expires_at,
        resolved_at=record.resolved_at,
    )
