"""Approximate model cost estimation.

Prices are indicative list prices in USD per million tokens, kept as a small,
explicit table so cost is a visible estimate rather than a silent zero. They are
**not** a billing record: verify against the provider before relying on them, and
update the table when a model's pricing changes. An unknown model yields ``0.0``
rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _Price:
    input_per_million: float
    output_per_million: float


_PRICES: dict[str, _Price] = {
    "gpt-4o-mini": _Price(input_per_million=0.15, output_per_million=0.60),
    "claude-3-5-haiku-latest": _Price(input_per_million=0.80, output_per_million=4.00),
    "mistral-small-latest": _Price(input_per_million=0.20, output_per_million=0.60),
    "deepseek-chat": _Price(input_per_million=0.27, output_per_million=1.10),
    "gemini-2.0-flash": _Price(input_per_million=0.10, output_per_million=0.40),
    "fake-1": _Price(input_per_million=0.0, output_per_million=0.0),
}


def estimate_cost_usd(model: str, *, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate the USD cost of one completion, or ``0.0`` for an unknown model."""
    price = _PRICES.get(model)
    if price is None:
        return 0.0
    billed_tokens = max(0, prompt_tokens) * price.input_per_million
    billed_tokens += max(0, completion_tokens) * price.output_per_million
    return billed_tokens / 1_000_000
