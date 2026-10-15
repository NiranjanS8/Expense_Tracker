"""The allowlist of read-only tools the assistant may invoke.

The registry is the only route from model output to an upstream request. A tool
is looked up by name; its arguments are validated by its own Pydantic model; and
the trusted user context supplies both the bearer token and the correlation id.
Model output can never widen an argument, choose a user, or introduce a tool that
is not registered here.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.errors import AppError, InvalidRequestError
from app.identity.user_context import UserContext
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.tools.budgets import BudgetStatusArguments, get_budget_status
from app.tools.common import ToolArguments
from app.tools.dashboard import (
    CategoryBreakdownArguments,
    DashboardSummaryArguments,
    get_category_breakdown,
    get_dashboard_summary,
)
from app.tools.expenses import (
    ExpenseSearchArguments,
    SpendingSummaryArguments,
    get_spending_summary,
    search_expenses,
)
from app.tools.goals import GoalProgressArguments, get_goal_progress
from app.tools.insights import ExistingInsightsArguments, get_existing_insights
from app.tools.recurring import RecurringExpenseArguments, get_recurring_expenses

logger = logging.getLogger(__name__)

_MAX_LOGGED_NAME_LENGTH = 64

ToolHandler = Callable[[ExpenseTrackerClient, UserContext, Any], Awaitable[BaseModel]]


@dataclass(frozen=True)
class ToolDefinition:
    """One allowlisted capability: its name, its contract and its implementation."""

    name: str
    description: str
    arguments_model: type[ToolArguments]
    handler: ToolHandler

    def arguments_schema(self) -> dict[str, Any]:
        """The JSON schema a model needs in order to form a valid call."""
        return self.arguments_model.model_json_schema()


class ToolRegistry:
    def __init__(self, definitions: Sequence[ToolDefinition]) -> None:
        self._definitions = tuple(definitions)
        self._by_name = {definition.name: definition for definition in self._definitions}
        if len(self._by_name) != len(self._definitions):
            raise ValueError("Tool names must be unique.")

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return self._definitions

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._by_name[name]
        except KeyError:
            logger.warning("event=tool_not_allowlisted tool=%s", name[:_MAX_LOGGED_NAME_LENGTH])
            raise InvalidRequestError("That tool is not available.") from None

    async def execute(
        self,
        name: str,
        *,
        client: ExpenseTrackerClient,
        context: UserContext,
        arguments: Mapping[str, object] | None = None,
    ) -> BaseModel:
        definition = self.get(name)
        validated = _validate_arguments(definition, arguments or {})
        started = time.perf_counter()

        try:
            result = await definition.handler(client, context, validated)
        except AppError as exception:
            _log_invocation(definition.name, context, started, outcome=exception.code)
            raise
        except Exception:
            _log_invocation(definition.name, context, started, outcome="unexpected_error")
            raise

        _log_invocation(definition.name, context, started, outcome="ok")
        return result


def build_tool_registry() -> ToolRegistry:
    """The single place where a capability becomes reachable by the model."""
    return ToolRegistry(
        (
            ToolDefinition(
                name="get_spending_summary",
                description=(
                    "Total amount and transaction count for expenses matching optional date, category, "
                    "amount and description filters. Use for 'how much did I spend' questions."
                ),
                arguments_model=SpendingSummaryArguments,
                handler=get_spending_summary,
            ),
            ToolDefinition(
                name="search_expenses",
                description=(
                    "List individual expenses matching the same filters, one page at a time. "
                    "Use for 'show me my expenses', 'largest expenses' or 'what did I buy at X' questions."
                ),
                arguments_model=ExpenseSearchArguments,
                handler=search_expenses,
            ),
            ToolDefinition(
                name="get_category_breakdown",
                description=(
                    "Spend per category for one month, largest first. "
                    "Use for 'where does my money go' or 'how much do I spend on X' questions."
                ),
                arguments_model=CategoryBreakdownArguments,
                handler=get_category_breakdown,
            ),
            ToolDefinition(
                name="get_budget_status",
                description=(
                    "Budget amount, spend, remaining amount and utilization for a month, a whole year, "
                    "or the current month. Use for 'how much of my budget is left' questions."
                ),
                arguments_model=BudgetStatusArguments,
                handler=get_budget_status,
            ),
            ToolDefinition(
                name="get_goal_progress",
                description=(
                    "Savings-goal progress, either one goal by id or every goal. "
                    "Use for 'how are my savings goals doing' questions."
                ),
                arguments_model=GoalProgressArguments,
                handler=get_goal_progress,
            ),
            ToolDefinition(
                name="get_recurring_expenses",
                description=(
                    "Recurring-expense rules, including their frequency, next run date and whether they "
                    "are active. Use for 'what subscriptions do I have' questions."
                ),
                arguments_model=RecurringExpenseArguments,
                handler=get_recurring_expenses,
            ),
            ToolDefinition(
                name="get_dashboard_summary",
                description=(
                    "The figures the application's dashboard shows for a month: monthly total, "
                    "transaction count and the most recent transactions."
                ),
                arguments_model=DashboardSummaryArguments,
                handler=get_dashboard_summary,
            ),
            ToolDefinition(
                name="get_existing_insights",
                description=(
                    "Insights the application already computed for a month, including the comparison with "
                    "the previous month. Use for 'why did my spending change' questions."
                ),
                arguments_model=ExistingInsightsArguments,
                handler=get_existing_insights,
            ),
        )
    )


def _validate_arguments(definition: ToolDefinition, arguments: Mapping[str, object]) -> ToolArguments:
    try:
        return definition.arguments_model.model_validate(arguments)
    except ValidationError as exception:
        logger.warning("event=tool_arguments_rejected tool=%s", definition.name)
        raise InvalidRequestError(
            "The arguments for that tool were not valid.",
            details=[
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exception.errors()
            ],
        ) from exception


def _log_invocation(tool: str, context: UserContext, started: float, *, outcome: str) -> None:
    # Trace metadata only: amounts, descriptions and category names never appear here.
    logger.info(
        "event=tool_invocation tool=%s user_id=%s outcome=%s duration_ms=%s",
        tool,
        context.user.user_id,
        outcome,
        round((time.perf_counter() - started) * 1000, 1),
    )
