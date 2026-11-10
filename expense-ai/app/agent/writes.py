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
from app.approvals.service import (
    CREATE_CATEGORY,
    CREATE_EXPENSE,
    SET_BUDGET,
    SET_RECURRING_STATUS,
)

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

_PAUSE_VERBS = frozenset({"pause", "paused", "stop", "suspend", "disable", "deactivate"})
_RESUME_VERBS = frozenset({"resume", "reactivate", "restart", "enable", "unpause"})
_STATUS_VERBS = _PAUSE_VERBS | _RESUME_VERBS
_RECURRING_NOUNS = frozenset({"recurring", "subscription", "subscriptions", "autopay"})
# Generic words a rule's description may carry that a caller would not repeat.
_RULE_NOUNS = frozenset({"recurring", "subscription", "subscriptions", "autopay", "payment"})
# Records a status verb could plausibly target instead of a recurring rule.
_OTHER_RECORDS = frozenset(
    {
        "budget",
        "budgets",
        "goal",
        "goals",
        "saving",
        "savings",
        "spend",
        "spending",
        "expense",
        "expenses",
        "account",
    }
)

_CATEGORY_NOUNS = frozenset({"category", "categories"})
_CATEGORY_VERBS = frozenset({"create", "add", "make"})
_EXPENSE_NOUNS = frozenset({"expense", "expenses", "purchase", "payment", "transaction", "budget", "budgets"})
_CATEGORY_NOUN = re.compile(r"\b(?:category|categories)\b", re.IGNORECASE)
_CATEGORY_LEAD = re.compile(r"^(?:(?:called|named|for|of|as)\s+)+", re.IGNORECASE)
_CATEGORY_ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)
_CATEGORY_LEADING_FILLER = re.compile(r"^(?:please|now)(?:\s+|$)", re.IGNORECASE)
_CATEGORY_TRAILING_FILLER = re.compile(r"\s+(?:please|thanks|thank you|now)$", re.IGNORECASE)
_FIRST_DIGIT = re.compile(r"\d")


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


@dataclass(frozen=True)
class RecurringRule:
    """One recurring expense, as the existing API describes it."""

    id: int
    description: str
    amount: float
    frequency: str
    active: bool
    next_execution_date: str | None
    category_name: str | None


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


def is_recurring_status_request(message: str) -> bool:
    """Whether the caller is asking to change a recurring rule's state."""
    tokens = _tokens(message)
    if tokens & _RECURRING_NOUNS:
        return bool(tokens & _STATUS_VERBS) or bool(tokens & {"turn", "switch"} and tokens & {"on", "off"})
    # A rule is often named without the word "subscription" ("pause my gym
    # membership"), so a status verb on the caller's own record is enough. Another
    # record being named keeps it off this path.
    return bool(tokens & _STATUS_VERBS) and "my" in tokens and not tokens & _OTHER_RECORDS


def extract_recurring_status(message: str) -> bool | None:
    """``False`` to pause, ``True`` to resume, ``None`` when this is not that ask."""
    if not is_recurring_status_request(message):
        return None
    tokens = _tokens(message)
    paused = bool(tokens & _PAUSE_VERBS or ({"turn", "switch"} & tokens and "off" in tokens))
    return not paused


def match_recurring_rule(message: str, rules: tuple[RecurringRule, ...]) -> RecurringRule | None:
    """The one rule the caller named, or the only rule they have.

    Returning ``None`` means the caller did not identify a single rule; the caller
    then asks which one instead of guessing. Two rules with the same name are
    ambiguous even if both match, so they are reported rather than picked.
    """
    tokens = _tokens(message)
    best: list[RecurringRule] = []
    best_size = 0

    for rule in rules:
        description_tokens = _tokens(rule.description) - _RULE_NOUNS
        category_tokens = _tokens(rule.category_name or "")
        if description_tokens and description_tokens <= tokens:
            matched = len(description_tokens)
        elif category_tokens and category_tokens <= tokens:
            matched = len(category_tokens)
        else:
            continue
        if matched > best_size:
            best = [rule]
            best_size = matched
        elif matched == best_size:
            best.append(rule)

    if len(best) == 1:
        return best[0]
    if not best and len(rules) == 1:
        return rules[0]
    return None


def recurring_intent(rule: RecurringRule, *, active: bool) -> WriteIntent:
    verb = "Resume" if active else "Pause"
    target_state = "active" if active else "paused"
    current_state = "active" if rule.active else "paused"

    return WriteIntent(
        action=SET_RECURRING_STATUS,
        resource_id=str(rule.id),
        arguments={"active": active},
        summary=f'{verb} the recurring expense "{rule.description}"',
        details=[
            {"label": "Recurring expense", "value": rule.description},
            {"label": "Amount", "value": format_money(rule.amount)},
            {"label": "Frequency", "value": rule.frequency.replace("_", " ").title() or "-"},
            {"label": "Category", "value": rule.category_name or "-"},
            {"label": "Next occurrence", "value": rule.next_execution_date or "-"},
            {"label": "Change", "value": f"{current_state.title()} -> {target_state.title()}"},
        ],
        consequences=(
            [
                "Future occurrences will be generated again from the next scheduled date.",
                "Expenses it already generated are unchanged.",
            ]
            if active
            else [
                "No future expenses will be generated from this rule.",
                "Expenses it already generated stay as they are.",
            ]
        ),
        message=(
            "Here is the recurring-expense change I parsed from your message. Review it and "
            "approve it to apply it. Nothing has been changed yet."
        ),
    )


def is_category_creation(message: str) -> bool:
    tokens = _tokens(message)
    if not tokens & _CATEGORY_NOUNS or not tokens & _CATEGORY_VERBS:
        return False
    # A mention of an expense or budget means the category is a detail of that
    # entry, not the thing being created.
    if tokens & _EXPENSE_NOUNS:
        return False

    amount = find_amount(message)
    if amount is None:
        return True
    # A bare number before the noun ("add 20 lunch to the Food category") is an
    # amount; one after it ("a category called 2026 travel") is part of the name.
    noun = _CATEGORY_NOUN.search(message)
    digit = _FIRST_DIGIT.search(message)
    return noun is not None and digit is not None and noun.start() < digit.start()


def extract_category_name(message: str) -> str | None:
    """The name the caller gave, taken literally; ``None`` when they gave none.

    Everything after the word "category" is the name, minus one leading connector
    ("called", "for", "of") and article, so unusual names survive exactly as typed
    instead of being rebuilt from tokens.
    """
    noun = _CATEGORY_NOUN.search(message)
    if noun is None:
        return None

    candidate = " ".join(message[noun.end() :].split()).strip(" .,:;\"'")
    candidate = _CATEGORY_LEADING_FILLER.sub("", candidate)
    candidate = _CATEGORY_LEAD.sub("", candidate)
    candidate = _CATEGORY_ARTICLE.sub("", candidate)
    candidate = _CATEGORY_TRAILING_FILLER.sub("", candidate)
    name = candidate.strip(" .,:;\"'")
    return name[:100] or None


def category_intent(name: str) -> WriteIntent:
    return WriteIntent(
        action=CREATE_CATEGORY,
        resource_id=None,
        arguments={"name": name},
        summary=f'New category "{name}"',
        details=[
            {"label": "Name", "value": name},
            {"label": "Type", "value": "Custom category"},
        ],
        consequences=[
            "Adds a category you can use on expenses and budgets.",
            "A name that already exists is rejected.",
        ],
        message=(
            "Here is the category I parsed from your message. Review it and approve it to "
            "create it. Nothing has been created yet."
        ),
    )


def _tokens(text: str) -> set[str]:
    return {match.strip(".-'&").lower() for match in _WORD.findall(text)}
