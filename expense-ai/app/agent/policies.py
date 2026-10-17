"""Deterministic policy decisions for the assistant.

Intent classification is a keyword gate, not a model call. It decides whether a
turn may use financial tools at all, which keeps chit-chat and capability
questions from spending tool calls and keeps the routing testable.
"""

from __future__ import annotations

DATA_INTENT = "data"
GENERAL_INTENT = "general"

# Words that signal a question about the user's own finances. Deliberately broad:
# a false positive only wastes a bounded tool call, whereas a false negative would
# refuse to look up data the user asked for.
_DATA_KEYWORDS = frozenset(
    {
        "spend",
        "spent",
        "spending",
        "expense",
        "expenses",
        "budget",
        "budgets",
        "goal",
        "goals",
        "saving",
        "savings",
        "recurring",
        "subscription",
        "subscriptions",
        "insight",
        "insights",
        "dashboard",
        "category",
        "categories",
        "transaction",
        "transactions",
        "cost",
        "costs",
        "total",
        "totals",
        "compare",
        "comparison",
        "trend",
        "trends",
        "largest",
        "biggest",
        "payment",
        "payments",
        "bill",
        "bills",
        "month",
        "months",
        "week",
        "weeks",
        "year",
        "years",
        "today",
        "yesterday",
    }
)

_DEFAULT_TITLE = "New conversation"


def classify_intent(message: str) -> str:
    """Return ``data`` when the turn is about the user's finances, else ``general``."""
    tokens = {token.strip(".,!?:;\"'()").lower() for token in message.split()}
    if tokens & _DATA_KEYWORDS:
        return DATA_INTENT
    lowered = message.lower()
    for phrase in ("how much", "how many", "where does my money"):
        if phrase in lowered:
            return DATA_INTENT
    return GENERAL_INTENT


def conversation_title(message: str, *, max_length: int) -> str:
    """A short, human-readable title derived from the first user message."""
    collapsed = " ".join(message.split())
    if not collapsed:
        return _DEFAULT_TITLE
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 1].rstrip() + "\u2026"
