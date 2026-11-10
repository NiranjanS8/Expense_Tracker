"""Deterministic policy decisions for the assistant.

Intent classification is a keyword gate, not a model call. It decides whether a
turn may use financial tools at all, which keeps chit-chat and capability
questions from spending tool calls and keeps the routing testable. It also
separates a request to *record* something into its own path, so such a turn can
never reach the tools that read data.
"""

from __future__ import annotations

DATA_INTENT = "data"
GENERAL_INTENT = "general"
DRAFT_INTENT = "draft"

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

# A request to record something is only treated as a draft when it names both an
# action and something recordable. The gate is deliberately conservative: when a
# turn is ambiguous it takes the read or conversational path, which never proposes
# values the caller did not supply.
_CREATE_VERBS = frozenset({"add", "record", "log", "create", "save", "enter", "track", "set"})
_ENTRY_NOUNS = frozenset(
    {
        "expense",
        "expenses",
        "spending",
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
    }
)

# "Add up my expenses" and "What should I set my budget to?" both pair a create
# verb with an entry noun, but neither asks for anything to be recorded.
# Two writes are not "record an entry" requests: changing a recurring rule's state
# and adding a category. They need their own conservative gates, because the same
# words in a question ("what subscriptions do I have?") must stay on the read path.
_STATUS_VERBS = frozenset(
    {
        "pause",
        "paused",
        "stop",
        "suspend",
        "disable",
        "deactivate",
        "resume",
        "reactivate",
        "restart",
        "enable",
        "unpause",
    }
)
_RECURRING_NOUNS = frozenset({"recurring", "subscription", "subscriptions", "autopay"})
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

_PHRASAL_EXCLUSIONS = ("add up", "log in", "sign in", "sign up")
_INTERROGATIVE_STARTS = frozenset(
    {
        "what",
        "how",
        "why",
        "when",
        "where",
        "which",
        "who",
        "whose",
        "should",
        "can",
        "could",
        "would",
        "do",
        "does",
        "did",
        "is",
        "are",
        "was",
        "were",
        "will",
        "may",
    }
)

_DEFAULT_TITLE = "New conversation"


def classify_intent(message: str) -> str:
    """Route the turn: ``draft``, ``data`` or ``general``.

    A record request wins over a data question, because "add 12.50 for coffee"
    contains the word *expense*-like nouns but asks for a form, not a lookup.
    """
    tokens = _tokenize(message)
    lowered = message.lower()

    if _is_draft_request(lowered, tokens):
        return DRAFT_INTENT
    if tokens & _DATA_KEYWORDS:
        return DATA_INTENT
    for phrase in ("how much", "how many", "where does my money"):
        if phrase in lowered:
            return DATA_INTENT
    return GENERAL_INTENT


def _tokenize(message: str) -> set[str]:
    return {token.strip(".,!?:;\"'()").lower() for token in message.split()}


def _is_draft_request(lowered: str, tokens: set[str]) -> bool:
    if any(phrase in lowered for phrase in _PHRASAL_EXCLUSIONS):
        return False
    words = lowered.split()
    if words and words[0].strip(".,!?:;\"'()") in _INTERROGATIVE_STARTS:
        return False
    if tokens & _CREATE_VERBS and tokens & _ENTRY_NOUNS:
        return True
    if tokens & _RECURRING_NOUNS and (
        tokens & _STATUS_VERBS or (tokens & {"turn", "switch"} and tokens & {"on", "off"})
    ):
        return True
    if tokens & _STATUS_VERBS and "my" in tokens and not tokens & _OTHER_RECORDS:
        return True
    return bool(tokens & _CATEGORY_NOUNS) and bool(tokens & _CATEGORY_VERBS)


def conversation_title(message: str, *, max_length: int) -> str:
    """A short, human-readable title derived from the first user message."""
    collapsed = " ".join(message.split())
    if not collapsed:
        return _DEFAULT_TITLE
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 1].rstrip() + "\u2026"
