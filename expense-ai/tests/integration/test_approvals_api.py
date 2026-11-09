"""Confirmed writes: propose, approve once, and fail safely.

The entire flow runs through the HTTP surface, with Spring Boot stubbed at the
transport. Nothing here uses a model: the proposal is parsed from the caller's
message, so these tests also prove the write path works with the provider down.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
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
) -> Responder:
    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == CURRENT_USER_PATH:
            return _user(request)
        if path == "/api/categories":
            return httpx.Response(200, json=categories if categories is not None else [])
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
