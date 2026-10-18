"""Deterministic draft extraction for form prefill.

The assistant never writes. When the caller asks it to record something, it turns
that request into a *draft*: a set of values for the application's own form. The
user reviews the draft and saves it through the normal screen, so a draft can
never become a record on its own.

Extraction is deterministic rather than model-driven on purpose. Every value in a
draft is traceable to the caller's own words, so the assistant cannot propose a
figure the user never typed; a request that carries no amount yields no draft at
all. Reading the amount, the date and the wording is therefore a small amount of
parsing, not a model call, and it holds even when the model provider is down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

EXPENSE_DRAFT = "expense"
BUDGET_DRAFT = "budget"

_START_YEAR = 2000
_MAX_DESCRIPTION_LENGTH = 120

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_YEAR_MONTH = re.compile(r"\b\d{4}-\d{2}\b")
_DAY_FIRST_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
_WORD = re.compile(r"[A-Za-z][A-Za-z'&.-]*")

# Words that carry no recordable meaning once the amount, the date and the action
# have been read off the message. A description built from what remains is always
# a subset of the caller's own words.
_FILLER = frozenset(
    {
        "add",
        "added",
        "record",
        "recorded",
        "log",
        "logged",
        "create",
        "created",
        "save",
        "saved",
        "enter",
        "entered",
        "track",
        "tracked",
        "set",
        "put",
        "please",
        "a",
        "an",
        "the",
        "for",
        "on",
        "at",
        "of",
        "to",
        "in",
        "into",
        "my",
        "me",
        "i",
        "expense",
        "expenses",
        "spending",
        "spend",
        "spent",
        "budget",
        "budgets",
        "transaction",
        "transactions",
        "purchase",
        "purchases",
        "bill",
        "bills",
        "payment",
        "payments",
        "amount",
        "worth",
        "rs",
        "inr",
        "usd",
        "today",
        "yesterday",
        "tomorrow",
        "this",
        "next",
        "last",
        "month",
        "months",
        "and",
        "with",
        "from",
        "as",
        "is",
        "was",
        "it",
    }
)


@dataclass(frozen=True)
class DraftProposal:
    """A form prefill the caller still has to save themselves."""

    kind: str
    fields: dict[str, Any]
    summary: str
    message: str


def extract_draft(message: str, *, today: date) -> DraftProposal | None:
    """Read a draft off ``message``, or ``None`` when it carries no amount."""
    amount = _find_amount(message)
    if amount is None or amount <= 0:
        return None
    if _lowered_words(message) & {"budget", "budgets"}:
        return _budget_draft(message, amount=amount, today=today)
    return _expense_draft(message, amount=amount, today=today)


def _expense_draft(message: str, *, amount: float, today: date) -> DraftProposal:
    expense_date = _resolve_date(message, today=today)
    description = _describe(message) or "Expense"
    return DraftProposal(
        kind=EXPENSE_DRAFT,
        fields={
            "amount": amount,
            "expenseDate": expense_date.isoformat(),
            "description": description,
            "categoryHint": description,
        },
        summary=f"Expense of {_money(amount)} for {description} on {expense_date.isoformat()}",
        message=(
            f"Here's a draft expense: {_money(amount)} for {description} on "
            f"{expense_date.isoformat()}. Nothing has been saved \u2014 review it in the "
            "expense form and press Save when it looks right."
        ),
    )


def _budget_draft(message: str, *, amount: float, today: date) -> DraftProposal:
    month = _resolve_month(message, today=today)
    return DraftProposal(
        kind=BUDGET_DRAFT,
        fields={"amount": amount, "budgetMonth": month},
        summary=f"Monthly budget of {_money(amount)} for {month}",
        message=(
            f"Here's a draft monthly budget: {_money(amount)} for {month}. "
            "Nothing has been saved \u2014 review it in the budget form and press Save when "
            "it looks right."
        ),
    )


def _find_amount(message: str) -> float | None:
    """The first explicit amount, ignoring anything that is part of a date."""
    scrubbed = _ISO_DATE.sub(" ", message)
    scrubbed = _YEAR_MONTH.sub(" ", scrubbed)
    scrubbed = _DAY_FIRST_DATE.sub(" ", scrubbed)
    match = _NUMBER.search(scrubbed)
    if match is None:
        return None
    return float(match.group(0).replace(",", ""))


def _resolve_date(message: str, *, today: date) -> date:
    iso = _ISO_DATE.search(message)
    if iso is not None:
        parsed = _parse_date(iso.group(0), "%Y-%m-%d")
        if parsed is not None:
            return parsed

    day_first = _DAY_FIRST_DATE.search(message)
    if day_first is not None:
        parsed = _parse_day_first(day_first, today=today)
        if parsed is not None:
            return parsed

    words = _lowered_words(message)
    if "yesterday" in words:
        return today - timedelta(days=1)
    if "tomorrow" in words:
        return today + timedelta(days=1)
    return today


def _parse_day_first(match: re.Match[str], *, today: date) -> date | None:
    day, month, year = match.group(1), match.group(2), match.group(3)
    resolved_year = today.year
    if year is not None:
        resolved_year = int(year) if len(year) == 4 else _START_YEAR + int(year)
    return _parse_date(f"{resolved_year:04d}-{int(month):02d}-{int(day):02d}", "%Y-%m-%d")


def _resolve_month(message: str, *, today: date) -> str:
    explicit = _YEAR_MONTH.search(message)
    if explicit is not None:
        return explicit.group(0)

    words = _lowered_words(message)
    if "next" in words and "month" in words:
        return _shift_month(today, 1)
    if "last" in words and "month" in words:
        return _shift_month(today, -1)
    return f"{today.year:04d}-{today.month:02d}"


def _shift_month(today: date, delta: int) -> str:
    index = today.year * 12 + (today.month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _describe(message: str) -> str:
    words = [word for word in _words(message) if word.lower() not in _FILLER]
    return " ".join(words).strip()[:_MAX_DESCRIPTION_LENGTH]


def _parse_date(value: str, pattern: str) -> date | None:
    try:
        return datetime.strptime(value, pattern).date()
    except ValueError:
        return None


def _words(message: str) -> list[str]:
    return [word for word in (match.strip(".-'&") for match in _WORD.findall(message)) if word]


def _lowered_words(message: str) -> set[str]:
    return {word.lower() for word in _words(message)}


def _money(amount: float) -> str:
    return f"{amount:,.2f}"
