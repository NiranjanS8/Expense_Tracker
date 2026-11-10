"""From proposal to confirmed write.

The flow is deliberately split in two:

* ``propose`` records what the caller asked for. It performs no write and makes no
  model call; the literal arguments come from the assistant's deterministic parser.
* ``approve`` executes exactly that record, once. The claim is a conditional
  database update, so a repeated or concurrent approval cannot create a duplicate.

A write that times out or receives a 5xx is reported as *unknown*, never retried:
the record may or may not exist, and only the owner can decide what to do next.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.approvals.binding import approval_hash
from app.approvals.repository import (
    EXECUTED,
    FAILED,
    PENDING,
    UNKNOWN,
    ApprovalRecord,
    ApprovalRepository,
)
from app.core.errors import (
    AppError,
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from app.core.security import AccessToken
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.observability.metrics import metrics

logger = logging.getLogger(__name__)

CREATE_EXPENSE = "create_expense"
SET_BUDGET = "set_budget"
SET_RECURRING_STATUS = "set_recurring_status"
CREATE_CATEGORY = "create_category"
SUPPORTED_ACTIONS = frozenset({CREATE_EXPENSE, SET_BUDGET, SET_RECURRING_STATUS, CREATE_CATEGORY})

_PAYMENT_METHODS = frozenset({"CASH", "CARD", "UPI", "BANK_TRANSFER", "WALLET", "OTHER"})
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INTEGER = re.compile(r"^\d+$")

_UNCERTAIN_MESSAGE = (
    "The request was sent but did not complete, so it may or may not have been saved. "
    "Check your records before trying again."
)


class UncertainOutcome(Exception):
    """The write reached the point where its effect cannot be determined."""

    def __init__(self, message: str = _UNCERTAIN_MESSAGE) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ExecutionOutcome:
    ok: bool
    message: str
    resource_id: str | None = None


class ApprovalService:
    def __init__(
        self,
        *,
        repository: ApprovalRepository,
        client: Callable[[], ExpenseTrackerClient],
        ttl_seconds: int,
    ) -> None:
        self._repository = repository
        self._client = client
        self._ttl_seconds = ttl_seconds

    async def propose(
        self,
        *,
        owner_id: int,
        conversation_id: str | None,
        action: str,
        resource_id: str | None,
        arguments: dict[str, Any],
        summary: str,
        details: list[dict[str, str]],
        consequences: list[str],
    ) -> ApprovalRecord:
        if action not in SUPPORTED_ACTIONS:
            raise InvalidRequestError("That change is not supported.")
        _validate_arguments(action, resource_id, arguments)

        digest = approval_hash(
            owner_id=owner_id,
            action=action,
            resource_id=resource_id,
            arguments=arguments,
        )
        record = await self._repository.create(
            owner_id=owner_id,
            conversation_id=conversation_id,
            action=action,
            resource_id=resource_id,
            arguments=arguments,
            arguments_hash=digest,
            summary=summary,
            details=details,
            consequences=consequences,
            ttl_seconds=self._ttl_seconds,
            now=datetime.now(UTC),
        )
        metrics.record_write_proposal(action=action)
        logger.info(
            "event=write_proposal_created approval_id=%s user_id=%s action=%s binding=%s",
            record.id,
            owner_id,
            action,
            digest[:12],
        )
        return record

    async def approve(
        self,
        *,
        owner_id: int,
        approval_id: str,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ApprovalRecord:
        now = datetime.now(UTC)
        record = await self._require(owner_id, approval_id)

        if record.status != PENDING:
            raise ConflictError(_not_pending_message(record.status))
        if record.expires_at <= now:
            await self._repository.mark_expired(owner_id, approval_id, now=now)
            raise ConflictError("This approval has expired. Ask again to create a new one.")
        if not self._binding_matches(record):
            logger.error("event=write_binding_mismatch approval_id=%s", approval_id)
            raise ConflictError("This approval no longer matches the change it described.")

        if not await self._repository.claim(owner_id, approval_id, now=now):
            # Lost the race to a concurrent approval; that request is executing.
            raise ConflictError(_not_pending_message("executing"))

        logger.info(
            "event=write_approved approval_id=%s user_id=%s action=%s binding=%s",
            approval_id,
            owner_id,
            record.action,
            record.arguments_hash[:12],
        )

        try:
            outcome = await self._execute(record, token=token, correlation_id=correlation_id)
        except UncertainOutcome as uncertain:
            await self._repository.resolve(
                owner_id,
                approval_id,
                status=UNKNOWN,
                outcome={"message": uncertain.message},
                now=datetime.now(UTC),
            )
            metrics.record_write_execution(action=record.action, outcome=UNKNOWN)
            logger.warning(
                "event=write_outcome_unknown approval_id=%s user_id=%s action=%s",
                approval_id,
                owner_id,
                record.action,
            )
            return await self._require(owner_id, approval_id)

        status = EXECUTED if outcome.ok else FAILED
        await self._repository.resolve(
            owner_id,
            approval_id,
            status=status,
            outcome={"message": outcome.message, "resourceId": outcome.resource_id},
            now=datetime.now(UTC),
        )
        metrics.record_write_execution(action=record.action, outcome=status)
        logger.info(
            "event=write_%s approval_id=%s user_id=%s action=%s resource_id=%s",
            "executed" if outcome.ok else "failed",
            approval_id,
            owner_id,
            record.action,
            outcome.resource_id,
        )
        return await self._require(owner_id, approval_id)

    async def cancel(self, *, owner_id: int, approval_id: str) -> ApprovalRecord:
        record = await self._require(owner_id, approval_id)
        now = datetime.now(UTC)

        if record.status != PENDING:
            raise ConflictError(_not_pending_message(record.status))
        if record.expires_at <= now:
            await self._repository.mark_expired(owner_id, approval_id, now=now)
            raise ConflictError("This approval has expired.")
        if not await self._repository.cancel(owner_id, approval_id, now=now):
            raise ConflictError(_not_pending_message("executing"))

        logger.info("event=write_cancelled approval_id=%s user_id=%s", approval_id, owner_id)
        return await self._require(owner_id, approval_id)

    async def get(self, *, owner_id: int, approval_id: str) -> ApprovalRecord:
        return await self._require(owner_id, approval_id)

    async def list_pending(self, *, owner_id: int, conversation_id: str) -> list[ApprovalRecord]:
        """Approvals the owner can still act on, so a reload does not lose them."""
        return await self._repository.list_pending_for_conversation(
            owner_id, conversation_id, now=datetime.now(UTC)
        )

    async def _require(self, owner_id: int, approval_id: str) -> ApprovalRecord:
        record = await self._repository.get_for_owner(owner_id, approval_id)
        if record is None:
            raise NotFoundError("Approval not found.")
        return record

    def _binding_matches(self, record: ApprovalRecord) -> bool:
        return (
            approval_hash(
                owner_id=record.owner_id,
                action=record.action,
                resource_id=record.resource_id,
                arguments=record.arguments,
            )
            == record.arguments_hash
        )

    async def _execute(
        self,
        record: ApprovalRecord,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        try:
            if record.action == CREATE_EXPENSE:
                return await self._create_expense(record, token=token, correlation_id=correlation_id)
            if record.action == SET_BUDGET:
                return await self._set_budget(record, token=token, correlation_id=correlation_id)
            if record.action == SET_RECURRING_STATUS:
                return await self._set_recurring_status(record, token=token, correlation_id=correlation_id)
            if record.action == CREATE_CATEGORY:
                return await self._create_category(record, token=token, correlation_id=correlation_id)
        except InvalidRequestError as exception:
            return ExecutionOutcome(ok=False, message=exception.message)
        except NotFoundError as exception:
            return ExecutionOutcome(ok=False, message=exception.message)
        except UnauthenticatedError:
            return ExecutionOutcome(
                ok=False,
                message="Your session is no longer valid, so nothing was saved. Please log in again.",
            )
        except RateLimitedError:
            return ExecutionOutcome(
                ok=False,
                message="The service is busy, so nothing was saved. Please try again in a moment.",
            )
        except (UpstreamTimeoutError, UpstreamUnavailableError):
            # Only a read can reach here; the write itself raises UncertainOutcome.
            return ExecutionOutcome(
                ok=False,
                message="A service was unavailable before anything was saved. Please try again.",
            )

        return ExecutionOutcome(ok=False, message="That change is not supported; nothing was saved.")

    async def _create_expense(
        self,
        record: ApprovalRecord,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        arguments = record.arguments
        category_id = arguments.get("categoryId")
        if category_id is not None and not await self._category_exists(
            category_id, token=token, correlation_id=correlation_id
        ):
            return ExecutionOutcome(ok=False, message="That category no longer exists, so nothing was saved.")

        created = await self._send_write(
            "POST",
            "/expenses",
            token=token,
            payload={
                "categoryId": category_id,
                "amount": _amount_number(arguments["amount"]),
                "expenseDate": arguments["expenseDate"],
                "description": arguments["description"],
                "paymentMethod": arguments["paymentMethod"],
            },
            correlation_id=correlation_id,
        )
        return ExecutionOutcome(
            ok=True,
            message=(
                f"Expense saved: {arguments['description']} for "
                f"{_money(arguments['amount'])} on {arguments['expenseDate']}."
            ),
            resource_id=_created_id(created),
        )

    async def _set_budget(
        self,
        record: ApprovalRecord,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        month = record.resource_id or ""
        payload = {
            "amount": _amount_number(record.arguments["amount"]),
            "budgetMonth": month,
        }
        exists = await self._budget_exists(month, token=token, correlation_id=correlation_id)

        if exists:
            updated = await self._send_write(
                "PUT",
                f"/budgets/{month}",
                token=token,
                payload=payload,
                correlation_id=correlation_id,
            )
        else:
            try:
                updated = await self._send_write(
                    "POST",
                    "/budgets",
                    token=token,
                    payload=payload,
                    correlation_id=correlation_id,
                )
            except InvalidRequestError:
                # Another writer created this month between the read and the
                # create. The intended end state is unchanged, so update once.
                if not await self._budget_exists(month, token=token, correlation_id=correlation_id):
                    raise
                updated = await self._send_write(
                    "PUT",
                    f"/budgets/{month}",
                    token=token,
                    payload=payload,
                    correlation_id=correlation_id,
                )

        return ExecutionOutcome(
            ok=True,
            message=f"Budget for {month} set to {_money(record.arguments['amount'])}.",
            resource_id=_created_id(updated) or month,
        )

    async def _send_write(
        self,
        method: str,
        path: str,
        *,
        token: AccessToken,
        payload: dict[str, object],
        correlation_id: str | None,
    ) -> object:
        """Send the write, converting transport ambiguity into an unknown outcome."""
        try:
            if method == "PATCH":
                return await self._client().patch_json(
                    path, token=token, payload=payload, correlation_id=correlation_id
                )
            if method == "PUT":
                return await self._client().put_json(
                    path, token=token, payload=payload, correlation_id=correlation_id
                )
            return await self._client().post_json(
                path, token=token, payload=payload, correlation_id=correlation_id
            )
        except (UpstreamTimeoutError, UpstreamUnavailableError) as exception:
            raise UncertainOutcome() from exception

    async def _category_exists(
        self,
        category_id: object,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> bool:
        body = await self._client().get_json(
            "/categories",
            token=token,
            correlation_id=correlation_id,
            missing_message="The category list is unavailable.",
        )
        if not isinstance(body, list):
            raise UpstreamUnavailableError()
        return any(
            isinstance(item, dict) and item.get("id") == category_id and isinstance(item.get("name"), str)
            for item in body
        )

    async def _budget_exists(
        self,
        month: str,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> bool:
        try:
            await self._client().get_json(
                f"/budgets/{month}",
                token=token,
                correlation_id=correlation_id,
                missing_message="No budget exists for that month.",
            )
        except NotFoundError:
            return False
        return True

    async def _set_recurring_status(
        self,
        record: ApprovalRecord,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        rule_id = record.resource_id or ""
        target = bool(record.arguments["active"])
        rule = await self._find_recurring_rule(rule_id, token=token, correlation_id=correlation_id)
        if rule is None:
            return ExecutionOutcome(
                ok=False,
                message="That recurring expense no longer exists, so nothing was changed.",
            )

        description = str(rule.get("description") or "That recurring expense")
        if bool(rule.get("active")) == target:
            return ExecutionOutcome(
                ok=True,
                message=(
                    f'"{description}" is already {"active" if target else "paused"}; '
                    "nothing needed to change."
                ),
                resource_id=rule_id,
            )

        try:
            await self._send_write(
                "PATCH",
                f"/recurring-expenses/{rule_id}/status",
                token=token,
                payload={"active": target},
                correlation_id=correlation_id,
            )
        except UncertainOutcome:
            # This change is declarative, so the rule itself can say whether it
            # applied. Reconcile instead of leaving an unresolvable unknown.
            return await self._reconcile_recurring(
                rule_id,
                description=description,
                target=target,
                token=token,
                correlation_id=correlation_id,
            )

        return ExecutionOutcome(
            ok=True,
            message=f'"{description}" is now {"active" if target else "paused"}.',
            resource_id=rule_id,
        )

    async def _reconcile_recurring(
        self,
        rule_id: str,
        *,
        description: str,
        target: bool,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        try:
            rule = await self._find_recurring_rule(rule_id, token=token, correlation_id=correlation_id)
        except AppError:
            raise UncertainOutcome() from None

        if rule is not None and bool(rule.get("active")) == target:
            return ExecutionOutcome(
                ok=True,
                message=f'Confirmed: "{description}" is now {"active" if target else "paused"}.',
                resource_id=rule_id,
            )
        return ExecutionOutcome(
            ok=False,
            message="The change did not go through, so nothing was changed. You can try again.",
            resource_id=rule_id,
        )

    async def _find_recurring_rule(
        self,
        rule_id: str,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> dict[str, Any] | None:
        body = await self._client().get_json(
            "/recurring-expenses",
            token=token,
            correlation_id=correlation_id,
            missing_message="The recurring expenses are unavailable.",
        )
        if not isinstance(body, list):
            raise UpstreamUnavailableError()
        for item in body:
            if isinstance(item, dict) and str(item.get("id")) == rule_id:
                return item
        return None

    async def _create_category(
        self,
        record: ApprovalRecord,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        name = str(record.arguments["name"])
        try:
            created = await self._send_write(
                "POST",
                "/categories",
                token=token,
                payload={"name": name},
                correlation_id=correlation_id,
            )
        except UncertainOutcome:
            # Category names are unique, so a re-read settles it: either the name is
            # present (created, or already there) or it is not.
            return await self._reconcile_category(name, token=token, correlation_id=correlation_id)

        return ExecutionOutcome(
            ok=True,
            message=f'Category "{name}" created.',
            resource_id=_created_id(created),
        )

    async def _reconcile_category(
        self,
        name: str,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> ExecutionOutcome:
        try:
            exists = await self._category_name_exists(name, token=token, correlation_id=correlation_id)
        except AppError:
            raise UncertainOutcome() from None

        if exists:
            return ExecutionOutcome(ok=True, message=f'Category "{name}" is present.')
        return ExecutionOutcome(ok=False, message="The category was not created. You can try again.")

    async def _category_name_exists(
        self,
        name: str,
        *,
        token: AccessToken,
        correlation_id: str | None,
    ) -> bool:
        body = await self._client().get_json(
            "/categories",
            token=token,
            correlation_id=correlation_id,
            missing_message="The category list is unavailable.",
        )
        if not isinstance(body, list):
            raise UpstreamUnavailableError()
        wanted = name.strip().lower()
        return any(
            isinstance(item, dict) and str(item.get("name", "")).strip().lower() == wanted for item in body
        )


def _validate_arguments(action: str, resource_id: str | None, arguments: dict[str, Any]) -> None:
    """Reject a proposal whose stored shape could not be executed safely."""
    if action in (CREATE_EXPENSE, SET_BUDGET) and _amount_number(arguments.get("amount")) <= 0:
        raise InvalidRequestError("The amount must be greater than zero.")

    if action == CREATE_EXPENSE:
        if not isinstance(arguments.get("description"), str):
            raise InvalidRequestError("The expense needs a description.")
        expense_date = arguments.get("expenseDate")
        if not isinstance(expense_date, str) or not _DATE.match(expense_date):
            raise InvalidRequestError("The expense date is not a valid date.")
        if arguments.get("paymentMethod") not in _PAYMENT_METHODS:
            raise InvalidRequestError("The payment method is not valid.")
        category_id = arguments.get("categoryId")
        if category_id is not None and not isinstance(category_id, int):
            raise InvalidRequestError("The category is not valid.")
        return

    if action == SET_BUDGET:
        month = resource_id or ""
        if not _MONTH.match(month) or arguments.get("budgetMonth") != month:
            raise InvalidRequestError("The budget month is not valid.")
        return

    if action == SET_RECURRING_STATUS:
        if not _INTEGER.match(resource_id or ""):
            raise InvalidRequestError("The recurring expense is not valid.")
        if not isinstance(arguments.get("active"), bool):
            raise InvalidRequestError("The new state is not valid.")
        return

    if action == CREATE_CATEGORY:
        name = arguments.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise InvalidRequestError("The category name is not valid.")
        return


def _amount_number(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError) as exception:
        raise InvalidRequestError("The amount is not valid.") from exception


def _created_id(body: object) -> str | None:
    if isinstance(body, dict):
        identifier = body.get("id")
        if isinstance(identifier, int):
            return str(identifier)
    return None


def _money(value: object) -> str:
    return f"{_amount_number(value):,.2f}"


def _not_pending_message(status: str) -> str:
    return {
        "executed": "This change has already been saved.",
        "failed": "This approval already ran and did not save anything.",
        "unknown": "This approval already ran and its outcome is unknown. Check your records first.",
        "cancelled": "This approval was cancelled.",
        "expired": "This approval has expired. Ask again to create a new one.",
        "executing": "This approval is already being processed.",
    }.get(status, "This approval has already been used.")
