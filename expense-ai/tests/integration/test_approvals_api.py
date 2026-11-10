"""Confirmed writes: propose, approve once, and fail safely.

The entire flow runs through the HTTP surface, with Spring Boot stubbed at the
transport. Nothing here uses a model: the proposal is parsed from the caller's
message, so these tests also prove the write path works with the provider down.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, tzinfo
from typing import Any, Self, cast

import httpx
import pytest

from app.core.config import Settings
from tests.conftest import CURRENT_USER_PATH, Harness, Responder, parse_sse

AUTH_HEADERS = {"Authorization": "Bearer token-1"}


@pytest.fixture
def write_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"write_operations_enabled": True})


@pytest.fixture
def write_harness(write_settings: Settings) -> Iterator[Harness]:
    with Harness(write_settings) as instance:
        yield instance


def _user(request: httpx.Request) -> httpx.Response:
    authorization = request.headers.get("authorization", "")
    user_id = 2 if authorization.endswith("token-2") else 1
    return httpx.Response(
        200,
        json={
            "id": user_id,
            "fullName": "Demo User",
            "email": f"demo{user_id}@expensetracker.com",
            "role": "USER",
        },
    )


def _responder(
    *,
    categories: list[dict[str, Any]] | None = None,
    budget_exists: bool = False,
    expense_status: int = 201,
    recurring: list[dict[str, Any]] | None = None,
    status_result: int = 200,
    on_status: Callable[[], None] | None = None,
    category_status: int = 201,
    category_body: dict[str, Any] | None = None,
) -> Responder:
    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == CURRENT_USER_PATH:
            return _user(request)
        if path == "/api/categories":
            if request.method == "POST":
                return httpx.Response(
                    category_status,
                    json=category_body
                    if category_body is not None
                    else {"id": 7, "name": "Lunch", "systemDefined": False},
                )
            return httpx.Response(200, json=categories if categories is not None else [])
        if path == "/api/recurring-expenses":
            return httpx.Response(200, json=recurring if recurring is not None else [])
        if path.startswith("/api/recurring-expenses/") and path.endswith("/status"):
            if on_status is not None:
                on_status()
            return httpx.Response(status_result, json={"id": 11, "active": True})
        if path == "/api/expenses" and request.method == "POST":
            return httpx.Response(expense_status, json={"id": 99})
        if path == "/api/budgets" and request.method == "POST":
            return httpx.Response(201, json={"id": 6})
        if path.startswith("/api/budgets/"):
            if not budget_exists:
                return httpx.Response(404, json={"message": "Budget not found"})
            if request.method == "PUT":
                return httpx.Response(200, json={"id": 5})
            return httpx.Response(200, json={"id": 5})
        raise AssertionError(f"unexpected upstream call: {request.method} {path}")

    return respond


def _propose(harness: Harness, message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    response = harness.client.post("/api/v1/chat", json={"message": message}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    by_name = {name: payload for name, payload in events}
    assert "proposal" in by_name, f"no proposal event in {[name for name, _ in events]}"
    return by_name["proposal"], by_name["message_complete"]


def _approve(
    harness: Harness,
    approval_id: str,
    *,
    headers: dict[str, str] = AUTH_HEADERS,
) -> tuple[int, dict[str, Any]]:
    response = harness.client.post(f"/api/v1/approvals/{approval_id}/approve", headers=headers)
    body = response.json()
    return response.status_code, cast(dict[str, Any], body if isinstance(body, dict) else {})


def test_a_record_request_only_proposes_and_writes_nothing(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())

    proposal, complete = _propose(harness, "Add a 12.50 coffee expense today by card")

    assert complete["termination"] == "proposed"
    assert proposal["action"] == "create_expense"
    assert proposal["id"]
    assert proposal["expiresAt"]
    details = {detail["label"]: detail["value"] for detail in proposal["details"]}
    assert details["Amount"] == "12.50"
    assert details["Payment method"] == "Card"
    assert harness.requests_to("/api/expenses") == []


def test_approval_executes_exactly_once(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())
    proposal, _ = _propose(harness, "Add a 12.50 coffee expense today by card")

    status, body = _approve(harness, proposal["id"])

    assert status == 200
    assert body["status"] == "executed"
    assert body["outcome"].startswith("Expense saved")

    writes = harness.requests_to("/api/expenses")
    assert len(writes) == 1
    assert writes[0].method == "POST"
    assert json.loads(writes[0].content) == {
        "categoryId": None,
        "amount": 12.5,
        "expenseDate": date.today().isoformat(),
        "description": "coffee",
        "paymentMethod": "CARD",
    }

    assert _approve(harness, proposal["id"])[0] == 409
    assert len(harness.requests_to("/api/expenses")) == 1


def test_another_user_cannot_approve(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())
    proposal, _ = _propose(harness, "Add a 12.50 coffee expense today")

    status, _ = _approve(harness, proposal["id"], headers={"Authorization": "Bearer token-2"})

    assert status == 404
    assert harness.requests_to("/api/expenses") == []


def test_an_expired_approval_is_not_executed(write_harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    harness = write_harness
    harness.respond_from(_responder())
    proposal, _ = _propose(harness, "Add a 12.50 coffee expense today")

    class _FutureDatetime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            return cls(2100, 1, 1, tzinfo=UTC)

    monkeypatch.setattr("app.approvals.service.datetime", _FutureDatetime)

    status, body = _approve(harness, proposal["id"])

    assert status == 409
    assert "expired" in body["message"].lower()
    assert harness.requests_to("/api/expenses") == []


def test_a_cancelled_approval_is_never_executed(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())
    proposal, _ = _propose(harness, "Add a 12.50 coffee expense today")

    cancelled = harness.client.post(f"/api/v1/approvals/{proposal['id']}/cancel", headers=AUTH_HEADERS)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    assert _approve(harness, proposal["id"])[0] == 409
    assert harness.requests_to("/api/expenses") == []


def test_an_unreachable_write_is_reported_as_unknown_and_not_retried(
    write_harness: Harness,
) -> None:
    harness = write_harness
    harness.respond_from(_responder())
    proposal, _ = _propose(harness, "Add a 12.50 coffee expense today")
    harness.respond_from(_responder(expense_status=503))

    status, body = _approve(harness, proposal["id"])

    assert status == 200
    assert body["status"] == "unknown"
    assert "may or may not" in body["outcome"]
    assert len(harness.requests_to("/api/expenses")) == 1

    assert _approve(harness, proposal["id"])[0] == 409


def test_a_budget_approval_creates_a_missing_month(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder(budget_exists=False))
    proposal, _ = _propose(harness, "Set my budget for next month to 5,000")

    assert proposal["action"] == "set_budget"
    _, body = _approve(harness, proposal["id"])

    assert body["status"] == "executed"
    creates = [r for r in harness.requests if r.url.path == "/api/budgets" and r.method == "POST"]
    assert len(creates) == 1
    assert json.loads(creates[0].content)["amount"] == 5000.0


def test_a_budget_approval_updates_an_existing_month(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder(budget_exists=True))
    proposal, _ = _propose(harness, "Set my budget for next month to 5,000")

    _, body = _approve(harness, proposal["id"])

    assert body["status"] == "executed"
    updates = [
        request
        for request in harness.requests
        if request.method == "PUT" and request.url.path.startswith("/api/budgets/")
    ]
    assert len(updates) == 1
    assert not [
        request
        for request in harness.requests
        if request.url.path == "/api/budgets" and request.method == "POST"
    ]


def test_a_category_deleted_after_the_proposal_stops_the_write(
    write_harness: Harness,
) -> None:
    harness = write_harness
    harness.respond_from(_responder(categories=[{"id": 1, "name": "Food"}]))
    proposal, _ = _propose(harness, "Add a 20 food expense today")

    assert proposal["details"][3]["value"] == "Food"
    harness.respond_from(_responder(categories=[{"id": 2, "name": "Transport"}]))

    _, body = _approve(harness, proposal["id"])

    assert body["status"] == "failed"
    assert "category no longer exists" in body["outcome"]
    assert harness.requests_to("/api/expenses") == []


def test_the_approval_surface_is_closed_when_writes_are_disabled(harness: Harness) -> None:
    harness.authenticate()

    blocked = harness.client.post("/api/v1/approvals/anything/approve", headers=AUTH_HEADERS)
    assert blocked.status_code == 404

    response = harness.client.post(
        "/api/v1/chat",
        json={"message": "Add a 12.50 coffee expense today"},
        headers=AUTH_HEADERS,
    )
    names = [name for name, _ in parse_sse(response.text)]
    assert "draft" in names
    assert "proposal" not in names


_RULES: list[dict[str, Any]] = [
    {
        "id": 11,
        "description": "Gym membership",
        "amount": 1500.0,
        "frequency": "MONTHLY",
        "active": True,
        "nextExecutionDate": "2026-12-01",
        "categoryName": "Health",
    },
    {
        "id": 12,
        "description": "Rent",
        "amount": 20000.0,
        "frequency": "MONTHLY",
        "active": True,
        "nextExecutionDate": "2026-12-01",
        "categoryName": "Housing",
    },
]


def _chat(harness: Harness, message: str) -> dict[str, Any]:
    response = harness.client.post("/api/v1/chat", json={"message": message}, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    assert "proposal" not in {name for name, _ in events}
    return {name: payload for name, payload in events}["message_complete"]


def _patches(harness: Harness) -> list[httpx.Request]:
    return [request for request in harness.requests if request.method == "PATCH"]


def test_pausing_a_recurring_expense_needs_approval_then_applies_once(
    write_harness: Harness,
) -> None:
    harness = write_harness
    harness.respond_from(_responder(recurring=[dict(rule) for rule in _RULES]))

    proposal, complete = _propose(harness, "Pause my gym membership subscription")

    assert complete["termination"] == "proposed"
    assert proposal["action"] == "set_recurring_status"
    assert {detail["label"]: detail["value"] for detail in proposal["details"]}["Change"] == (
        "Active -> Paused"
    )
    assert _patches(harness) == []

    status, body = _approve(harness, proposal["id"])

    assert (status, body["status"]) == (200, "executed")
    patches = _patches(harness)
    assert len(patches) == 1
    assert patches[0].url.path == "/api/recurring-expenses/11/status"
    assert json.loads(patches[0].content) == {"active": False}


def test_an_ambiguous_recurring_request_asks_which_rule_instead_of_guessing(
    write_harness: Harness,
) -> None:
    harness = write_harness
    harness.respond_from(_responder(recurring=[dict(rule) for rule in _RULES]))

    complete = _chat(harness, "Pause my subscription")

    assert complete["termination"] == "needs_target"
    assert "Which one" in complete["content"]
    assert _patches(harness) == []


def test_the_only_recurring_expense_is_used_when_it_is_not_named(
    write_harness: Harness,
) -> None:
    harness = write_harness
    harness.respond_from(_responder(recurring=[dict(_RULES[0])]))

    proposal, _ = _propose(harness, "Pause my subscription")

    assert proposal["action"] == "set_recurring_status"
    assert "Gym membership" in proposal["summary"]


def test_a_rule_already_in_the_target_state_is_not_proposed(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder(recurring=[dict(_RULES[0], active=False)]))

    complete = _chat(harness, "Pause my gym membership")

    assert complete["termination"] == "answered"
    assert "already paused" in complete["content"]
    assert _patches(harness) == []


def test_a_rule_paused_after_the_proposal_is_not_written(write_harness: Harness) -> None:
    harness = write_harness
    rules = [dict(_RULES[0])]
    harness.respond_from(_responder(recurring=rules))
    proposal, _ = _propose(harness, "Pause my gym membership")

    rules[0]["active"] = False
    _, body = _approve(harness, proposal["id"])

    assert body["status"] == "executed"
    assert "already" in body["outcome"]
    assert _patches(harness) == []


def test_a_lost_status_response_is_reconciled_from_the_rule(write_harness: Harness) -> None:
    harness = write_harness
    rules = [dict(_RULES[0])]
    harness.respond_from(_responder(recurring=rules))
    proposal, _ = _propose(harness, "Pause my gym membership")

    def apply_the_change() -> None:
        rules[0]["active"] = False

    harness.respond_from(_responder(recurring=rules, status_result=503, on_status=apply_the_change))
    status, body = _approve(harness, proposal["id"])

    assert (status, body["status"]) == (200, "executed")
    assert body["outcome"].startswith("Confirmed")
    assert len(_patches(harness)) == 1


def test_creating_a_category_needs_approval(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())

    proposal, _ = _propose(harness, "Create a category called Coffee & Snacks")

    assert proposal["action"] == "create_category"
    assert {detail["label"]: detail["value"] for detail in proposal["details"]}["Name"] == ("Coffee & Snacks")
    assert not [
        request
        for request in harness.requests
        if request.method == "POST" and request.url.path == "/api/categories"
    ]

    status, body = _approve(harness, proposal["id"])

    assert (status, body["status"]) == (200, "executed")
    created = [
        request
        for request in harness.requests
        if request.method == "POST" and request.url.path == "/api/categories"
    ]
    assert len(created) == 1
    assert json.loads(created[0].content) == {"name": "Coffee & Snacks"}


def test_a_category_request_without_a_name_asks_for_one(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())

    complete = _chat(harness, "Create a new category please")

    assert complete["termination"] == "needs_target"
    assert "called" in complete["content"]


def test_a_rejected_category_reports_the_backend_message(write_harness: Harness) -> None:
    harness = write_harness
    harness.respond_from(_responder())
    proposal, _ = _propose(harness, "Create a category called Lunch")

    harness.respond_from(
        _responder(
            category_status=400,
            category_body={"message": "Category with this name already exists", "details": []},
        )
    )
    _, body = _approve(harness, proposal["id"])

    assert body["status"] == "failed"
    assert "already exists" in body["outcome"]
