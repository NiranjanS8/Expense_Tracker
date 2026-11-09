"""An approval is bound to one owner, action, resource and argument set."""

from __future__ import annotations

from typing import Any

from app.approvals.binding import approval_hash, canonical_json

_DEFAULT_ARGUMENTS = {"amount": "500.00", "budgetMonth": "2026-12"}


def _hash(
    *,
    owner_id: int = 7,
    action: str = "set_budget",
    resource_id: str | None = "2026-12",
    arguments: dict[str, Any] | None = None,
) -> str:
    return approval_hash(
        owner_id=owner_id,
        action=action,
        resource_id=resource_id,
        arguments=_DEFAULT_ARGUMENTS if arguments is None else arguments,
    )


def test_canonical_json_is_stable_and_order_independent() -> None:
    assert canonical_json({"b": 2, "a": 1}) == canonical_json({"a": 1, "b": 2})
    assert canonical_json({"a": 1}) == '{"a":1}'


def test_the_same_change_yields_the_same_hash() -> None:
    assert _hash() == _hash()


def test_a_different_owner_cannot_reuse_the_approval() -> None:
    assert _hash(owner_id=8) != _hash()


def test_a_different_resource_cannot_reuse_the_approval() -> None:
    assert _hash(resource_id="2027-01") != _hash()


def test_a_different_action_cannot_reuse_the_approval() -> None:
    assert _hash(action="create_expense") != _hash()


def test_changed_arguments_cannot_reuse_the_approval() -> None:
    assert _hash(arguments={"amount": "500.01", "budgetMonth": "2026-12"}) != _hash()
