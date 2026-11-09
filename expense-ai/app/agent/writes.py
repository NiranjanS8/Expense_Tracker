"""Deterministic parsing of a change the caller explicitly asked for.

The model never produces these arguments. Every value is read out of the caller's
own message with the same parsing the draft path uses, so a write proposal cannot
contain a figure, date or description the user did not type. Where the message is
silent, the proposal says so rather than inventing a value: the payment method is
reported as unspecified and a category is only chosen when the user named one.

A request that cannot be parsed into a complete write yields ``None``; the caller
then falls back to a form draft, which saves nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.agent.drafts import describe, find_amount, format_money, resolve_date, resolve_month
from app.approvals.service import CREATE_EXPENSE, SET_BUDGET

_WORD = re.compile(r"[A-Za-z][A-Za-z'&.-]*")

# Tokens a write parser has already interpreted. Removing them keeps the
# description to the words that actually name the purchase.
_IGNORED_DESCRIPTION = frozenset(
    {
        "by",
        "with",
        "paid",
        "pay",
        "paying",
        "using",
        "via",
        "cash",
        "card",
        "credit",
        "debit",
        "upi",
        "gpay",
        "phonepe",
        "paytm",
        "wallet",
        "neft",
        "imps",
        "rtgs",
        "transfer",
        "bank",
    }
)

_PAYMENT_LABELS = {
    "CASH": "Cash",
    "CARD": "Card",
    "UPI": "UPI",
    "BANK_TRANSFER": "Bank transfer",
    "WALLET": "Wallet",
    "OTHER": "Other",
}


@dataclass(frozen=True)
class CategoryOption:
    id: int
    name: str


@dataclass(frozen=True)
class WriteIntent:
    """A change the caller may approve; it has no effect until they do."""

    action: str
    resource_id: str | None
    arguments: dict[str, Any]
    summary: str
    details: list[dict[str, str]]
    consequences: list[str]
    message: str


def extract_write(
    message: str,
    *,
    today: date,
    categories: tuple[CategoryOption, ...] = (),
) -> WriteIntent | None:
    amount = find_amount(message)
    if amount is None or amount <= 0:
        return None
    if {"budget", "budgets"} & _tokens(message):
        return _budget_intent(message, amount=amount, today=today)
    return _expense_intent(message, amount=amount, today=today, categories=categories)


def _expense_intent(
    message: str,
    *,
    amount: float,
    today: date,
    categories: tuple[CategoryOption, ...],
) -> WriteIntent:
    expense_date = resolve_date(message, today=today)
    description = describe(message, ignored=_IGNORED_DESCRIPTION) or "Expense"
    payment_method, payment_stated = _payment_method(message)
    category = _match_category(message, categories)
    money = format_money(amount)

    return WriteIntent(
        action=CREATE_EXPENSE,
        resource_id=None,
        arguments={
            "amount": f"{amount:.2f}",
            "expenseDate": expense_date.isoformat(),
            "description": description,
            "categoryId": category.id if category is not None else None,
            "paymentMethod": payment_method,
        },
        summary=f"New expense of {money} for {description} on {expense_date.isoformat()}",
        details=[
            {"label": "Amount", "value": money},
            {"label": "Date", "value": expense_date.isoformat()},
            {"label": "Description", "value": description},
            {
                "label": "Category",
                "value": (category.name if category is not None else "Chosen by your smart-category rules"),
            },
            {
                "label": "Payment method",
                "value": _payment_value(payment_method, stated=payment_stated),
            },
        ],
        consequences=[
            "This adds one expense to your records.",
            "You can edit or delete it from the Expenses screen afterwards.",
        ],
        message=(
            "Here is the expense I parsed from your message. Review the values and "
            "approve it to save it. Nothing has been saved yet."
        ),
    )


def _budget_intent(message: str, *, amount: float, today: date) -> WriteIntent:
    month = resolve_month(message, today=today)
    money = format_money(amount)

    return WriteIntent(
        action=SET_BUDGET,
        resource_id=month,
        arguments={"amount": f"{amount:.2f}", "budgetMonth": month},
        summary=f"Monthly budget of {money} for {month}",
        details=[
            {"label": "Amount", "value": money},
            {"label": "Month", "value": month},
        ],
        consequences=[
            f"The monthly budget for {month} will be set to {money}.",
            "An existing budget for that month is replaced; otherwise a new one is created.",
        ],
        message=(
            "Here is the budget I parsed from your message. Review the values and "
            "approve it to save it. Nothing has been saved yet."
        ),
    )


def _match_category(
    message: str,
    categories: tuple[CategoryOption, ...],
) -> CategoryOption | None:
    """The user's own category whose name is fully present in the message.

    Deliberately literal: an unsaid category is left to the backend's smart
    category rules rather than guessed from the description.
    """
    tokens = _tokens(message)
    best: CategoryOption | None = None
    best_size = 0
    for category in categories:
        name_tokens = _tokens(category.name)
        if name_tokens and name_tokens <= tokens and len(name_tokens) > best_size:
            best = category
            best_size = len(name_tokens)
    return best


def _payment_method(message: str) -> tuple[str, bool]:
    lowered = message.lower()
    tokens = _tokens(message)

    if "bank transfer" in lowered or tokens & {"neft", "imps", "rtgs"}:
        return "BANK_TRANSFER", True
    if tokens & {"upi", "gpay", "phonepe", "paytm"}:
        return "UPI", True
    if "cash" in tokens:
        return "CASH", True
    if tokens & {"card", "credit", "debit"}:
        return "CARD", True
    if "wallet" in tokens:
        return "WALLET", True
    return "OTHER", False


def _payment_value(method: str, *, stated: bool) -> str:
    label = _PAYMENT_LABELS.get(method, method.title())
    return label if stated else f"{label} (not specified)"


def _tokens(text: str) -> set[str]:
    return {match.strip(".-'&").lower() for match in _WORD.findall(text)}
