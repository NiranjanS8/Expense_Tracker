"""Registry tests: the allowlist, argument gating and the trace metadata emitted."""

from __future__ import annotations

import logging

import pytest

from app.core.errors import InvalidRequestError, UpstreamUnavailableError
from app.tools import ToolRegistry, build_tool_registry
from app.tools.expenses import SpendingSummary
from tests.conftest import StubbedUpstream

EXPECTED_TOOL_NAMES = (
    "get_spending_summary",
    "search_expenses",
    "get_category_breakdown",
    "get_budget_status",
    "get_goal_progress",
    "get_recurring_expenses",
    "get_dashboard_summary",
    "get_existing_insights",
)

SUMMARY_BODY: dict[str, object] = {
    "totalAmount": 1234.56,
    "transactionCount": 2,
    "startDate": None,
    "endDate": None,
}

INVOCATION_LOGGER = "app.tools.registry"


def test_registry_exposes_exactly_the_planned_read_only_tools() -> None:
    definitions = build_tool_registry().definitions

    assert tuple(definition.name for definition in definitions) == EXPECTED_TOOL_NAMES


def test_every_tool_is_documented_and_typed() -> None:
    for definition in build_tool_registry().definitions:
        assert definition.description
        schema = definition.arguments_schema()
        assert schema["additionalProperties"] is False


def test_duplicate_tool_names_are_rejected_at_construction() -> None:
    definition = build_tool_registry().definitions[0]

    with pytest.raises(ValueError, match="unique"):
        ToolRegistry((definition, definition))


async def test_an_unlisted_tool_is_rejected_before_any_request(
    upstream: StubbedUpstream,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        caplog.at_level(logging.WARNING, logger=INVOCATION_LOGGER),
        pytest.raises(InvalidRequestError, match="not available"),
    ):
        await build_tool_registry().execute(
            "drop_the_database",
            client=upstream.client,
            context=upstream.context,
        )

    assert upstream.requests == []
    assert "drop_the_database" in caplog.text


async def test_identity_arguments_are_rejected_before_any_request(upstream: StubbedUpstream) -> None:
    with pytest.raises(InvalidRequestError) as error:
        await build_tool_registry().execute(
            "get_spending_summary",
            client=upstream.client,
            context=upstream.context,
            arguments={"userId": 2},
        )

    assert upstream.requests == []
    assert any("userId" in detail for detail in error.value.details)


async def test_invalid_arguments_are_reported_with_safe_details(upstream: StubbedUpstream) -> None:
    with pytest.raises(InvalidRequestError) as error:
        await build_tool_registry().execute(
            "get_spending_summary",
            client=upstream.client,
            context=upstream.context,
            arguments={"start_date": "yesterday"},
        )

    assert upstream.requests == []
    assert any(detail.startswith("start_date:") for detail in error.value.details)


async def test_execute_dispatches_to_the_registered_tool(upstream: StubbedUpstream) -> None:
    upstream.respond_with(200, SUMMARY_BODY)

    result = await build_tool_registry().execute(
        "get_spending_summary",
        client=upstream.client,
        context=upstream.context,
        arguments={"search": "coffee"},
    )

    assert isinstance(result, SpendingSummary)
    assert dict(upstream.only_request().url.params) == {"search": "coffee"}


async def test_a_successful_invocation_logs_trace_metadata_only(
    upstream: StubbedUpstream,
    caplog: pytest.LogCaptureFixture,
) -> None:
    upstream.respond_with(200, SUMMARY_BODY)

    with caplog.at_level(logging.INFO, logger=INVOCATION_LOGGER):
        await build_tool_registry().execute(
            "get_spending_summary",
            client=upstream.client,
            context=upstream.context,
        )

    message = next(
        record.getMessage() for record in caplog.records if "tool_invocation" in record.getMessage()
    )
    assert "tool=get_spending_summary" in message
    assert "user_id=1" in message
    assert "outcome=ok" in message
    assert "duration_ms=" in message
    assert "1234.56" not in message


async def test_a_failed_invocation_logs_its_typed_error_code(
    upstream: StubbedUpstream,
    caplog: pytest.LogCaptureFixture,
) -> None:
    upstream.respond_with(500)

    with caplog.at_level(logging.INFO, logger=INVOCATION_LOGGER), pytest.raises(UpstreamUnavailableError):
        await build_tool_registry().execute(
            "get_spending_summary",
            client=upstream.client,
            context=upstream.context,
        )

    assert "outcome=upstream_unavailable" in caplog.text
