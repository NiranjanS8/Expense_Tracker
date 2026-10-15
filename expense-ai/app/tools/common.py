"""Shared building blocks for the read-only tool layer.

Tool argument models forbid unknown fields. That is a security control rather
than a convenience: a model that invents ``userId`` or ``email`` receives a
validation error instead of another user's data. No tool accepts an identity
argument at all - the caller's bearer token decides the scope of every upstream
request.

Every bound the model could otherwise push past lives here, in one place, so it
can be tested directly: date ranges, amount ranges, pagination, free-text length
and the size of the list endpoints Spring Boot does not paginate.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, cast

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints, ValidationError
from pydantic.alias_generators import to_camel

from app.core.errors import UpstreamUnavailableError

logger = logging.getLogger(__name__)

MAX_DATE_RANGE_DAYS = 731
MAX_SEARCH_LENGTH = 200
MAX_PAGE_SIZE = 100
MAX_PAGE_INDEX = 1_000
MAX_LIST_ITEMS = 200

MIN_MONTH = "2000-01"
MAX_MONTH = "2100-12"

_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _validate_month_range(value: str) -> str:
    if not MIN_MONTH <= value <= MAX_MONTH:
        raise ValueError(f"must be between {MIN_MONTH} and {MAX_MONTH}")
    return value


Month = Annotated[str, StringConstraints(pattern=_MONTH_PATTERN), AfterValidator(_validate_month_range)]


class ToolArguments(BaseModel):
    """Base for the arguments of every tool.

    ``extra="forbid"`` rejects any field a tool does not declare, so an
    invented identity or scope argument fails validation instead of being
    silently ignored.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class UpstreamModel(BaseModel):
    """Base for payloads decoded from Spring Boot and for the results tools return.

    Reading accepts the camelCase names Java emits; the Python-side names stay
    snake_case, so nothing above this layer has to know about Java naming. Fields
    added to an upstream response are ignored rather than treated as breakage.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )


class ExpenseItem(UpstreamModel):
    """A single expense as exposed by the existing API."""

    id: int
    category_id: int
    category_name: str
    amount: Decimal
    expense_date: date
    description: str | None = None
    payment_method: str | None = None


class CategorySpending(UpstreamModel):
    """Aggregated spend for one category."""

    category_id: int | None = None
    category_name: str
    total_amount: Decimal


def validate_date_range(start_date: date | None, end_date: date | None) -> None:
    """Reject inverted or unbounded periods before they reach Spring Boot."""
    if start_date is None or end_date is None:
        return
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    if (end_date - start_date).days > MAX_DATE_RANGE_DAYS:
        raise ValueError(f"date range must not exceed {MAX_DATE_RANGE_DAYS} days")


def validate_amount_range(min_amount: Decimal | None, max_amount: Decimal | None) -> None:
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise ValueError("min_amount must not be greater than max_amount")


def compact_params(values: Mapping[str, object | None]) -> dict[str, str | int | float]:
    """Drop unset filters so a request carries only the arguments actually given."""
    return {key: cast("str | int | float", value) for key, value in values.items() if value is not None}


def decimal_param(value: Decimal | None) -> str | None:
    """Amounts travel as decimal strings so float encoding cannot lose precision."""
    return None if value is None else str(value)


def parse_upstream[Model: BaseModel](payload: object, model: type[Model], *, tool: str) -> Model:
    """Validate an upstream object, turning shape drift into a safe error."""
    try:
        return model.model_validate(payload)
    except ValidationError as exception:
        logger.warning("event=tool_payload_drift tool=%s", tool)
        raise UpstreamUnavailableError() from exception


def parse_upstream_list[Model: BaseModel](payload: object, model: type[Model], *, tool: str) -> list[Model]:
    """Validate an upstream array, turning shape drift into a safe error."""
    if not isinstance(payload, list):
        logger.warning("event=tool_payload_drift tool=%s", tool)
        raise UpstreamUnavailableError()

    try:
        return [model.model_validate(entry) for entry in payload]
    except ValidationError as exception:
        logger.warning("event=tool_payload_drift tool=%s", tool)
        raise UpstreamUnavailableError() from exception
