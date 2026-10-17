"""Unit tests for approximate model cost estimation."""

from __future__ import annotations

import pytest

from app.observability.cost import estimate_cost_usd


def test_known_model_cost_is_derived_from_tokens() -> None:
    cost = estimate_cost_usd("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)

    assert cost == pytest.approx(0.75)


def test_unknown_model_is_free_rather_than_guessed() -> None:
    assert estimate_cost_usd("mystery-1", prompt_tokens=10_000, completion_tokens=10_000) == 0.0


def test_negative_token_counts_are_clamped() -> None:
    assert estimate_cost_usd("gpt-4o-mini", prompt_tokens=-5, completion_tokens=-5) == 0.0
