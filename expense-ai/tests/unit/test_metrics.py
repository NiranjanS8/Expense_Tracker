"""Unit tests for the in-process metrics registry."""

from __future__ import annotations

import pytest

from app.observability.metrics import MetricsRegistry


def test_counters_render_in_prometheus_text() -> None:
    registry = MetricsRegistry()
    registry.increment("expense_ai_example_total", {"outcome": "ok"})
    registry.increment("expense_ai_example_total", {"outcome": "ok"})

    rendered = registry.render()

    assert "# TYPE expense_ai_example_total counter" in rendered
    assert 'expense_ai_example_total{outcome="ok"} 2' in rendered


def test_histogram_buckets_are_cumulative() -> None:
    registry = MetricsRegistry()
    registry.observe("expense_ai_latency_seconds", 0.03)
    registry.observe("expense_ai_latency_seconds", 0.4)

    rendered = registry.render()

    assert 'expense_ai_latency_seconds_bucket{le="0.05"} 1' in rendered
    assert 'expense_ai_latency_seconds_bucket{le="0.1"} 1' in rendered
    assert 'expense_ai_latency_seconds_bucket{le="0.5"} 2' in rendered
    assert 'expense_ai_latency_seconds_bucket{le="+Inf"} 2' in rendered
    assert "expense_ai_latency_seconds_count 2" in rendered


def test_histogram_sum_tracks_total_time() -> None:
    registry = MetricsRegistry()
    registry.observe("expense_ai_latency_seconds", 0.25, {"route": "/x"})
    registry.observe("expense_ai_latency_seconds", 0.25, {"route": "/x"})

    rendered = registry.render()
    sum_line = next(
        line for line in rendered.splitlines() if line.startswith("expense_ai_latency_seconds_sum")
    )

    assert float(sum_line.split()[-1]) == pytest.approx(0.5)


def test_label_values_are_escaped() -> None:
    registry = MetricsRegistry()
    registry.increment("expense_ai_example_total", {"route": '/a"b\\c'})

    assert 'route="/a\\"b\\\\c"' in registry.render()


def test_reset_clears_every_series() -> None:
    registry = MetricsRegistry()
    registry.increment("expense_ai_example_total")
    registry.observe("expense_ai_latency_seconds", 0.1)

    registry.reset()

    assert registry.render() == ""


def test_domain_helpers_record_bounded_labels() -> None:
    registry = MetricsRegistry()
    registry.record_tool_call(tool="get_spending_summary", outcome="ok", duration_seconds=0.2)
    registry.record_chat_turn(outcome="answered", duration_seconds=1.5)
    registry.record_http_request(method="post", route="/api/v1/chat", status=200, duration_seconds=1.2)
    registry.record_rate_limit_rejection(scope="http")
    registry.record_auth_denial(reason="unauthenticated")

    assert (
        registry.counter_value(
            "expense_ai_tool_calls_total", {"tool": "get_spending_summary", "outcome": "ok"}
        )
        == 1
    )
    assert (
        registry.histogram_count("expense_ai_tool_call_duration_seconds", {"tool": "get_spending_summary"})
        == 1
    )
    assert registry.counter_value("expense_ai_chat_turns_total", {"outcome": "answered"}) == 1
    assert (
        registry.counter_value(
            "expense_ai_http_requests_total", {"method": "POST", "route": "/api/v1/chat", "status": "200"}
        )
        == 1
    )
    assert registry.counter_value("expense_ai_rate_limit_rejections_total", {"scope": "http"}) == 1
    assert registry.counter_value("expense_ai_auth_denials_total", {"reason": "unauthenticated"}) == 1


def test_model_tokens_are_counted_by_kind() -> None:
    registry = MetricsRegistry()
    registry.record_model_call(
        provider="openai",
        node="plan",
        outcome="ok",
        duration_seconds=0.5,
        prompt_tokens=100,
        completion_tokens=20,
    )

    assert (
        registry.counter_value("expense_ai_model_tokens_total", {"provider": "openai", "kind": "prompt"})
        == 100
    )
    assert (
        registry.counter_value("expense_ai_model_tokens_total", {"provider": "openai", "kind": "completion"})
        == 20
    )


def test_zero_cost_records_no_series() -> None:
    registry = MetricsRegistry()
    registry.record_model_cost(provider="fake", model="fake-1", cost_usd=0.0)

    assert "expense_ai_model_cost_usd_total" not in registry.render()
