"""A minimal, dependency-free metrics registry.

Counters and histograms live in memory and render in the Prometheus text
exposition format. There is no metrics server and no dependency beyond the
standard library: a scrape endpoint reads :func:`MetricsRegistry.render`, and
deployment decides who may reach it.

Label values are always drawn from a small, closed set (route templates, tool
names, outcomes), so series cardinality stays bounded. Financial amounts,
descriptions and user identifiers are never used as labels.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass

PROMETHEUS_MEDIA_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# Fixed latency buckets (seconds). Fixed so these series never grow unbounded.
SECONDS_BUCKETS: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

LabelKey = tuple[tuple[str, str], ...]

_METRIC_HELP: dict[str, str] = {
    "expense_ai_http_requests_total": "HTTP requests handled, by method, route and status.",
    "expense_ai_http_request_duration_seconds": "HTTP request latency, by method and route.",
    "expense_ai_chat_turns_total": "Assistant turns completed, by outcome.",
    "expense_ai_chat_turn_duration_seconds": "Assistant turn latency.",
    "expense_ai_tool_calls_total": "Tool calls, by tool and outcome.",
    "expense_ai_tool_call_duration_seconds": "Tool call latency, by tool.",
    "expense_ai_model_calls_total": "Model calls, by provider, node and outcome.",
    "expense_ai_model_call_duration_seconds": "Model call latency, by provider and node.",
    "expense_ai_model_tokens_total": "Model tokens consumed, by provider and kind.",
    "expense_ai_model_cost_usd_total": "Estimated model cost in USD, by provider and model.",
    "expense_ai_rate_limit_rejections_total": "Requests rejected by a rate limiter.",
    "expense_ai_auth_denials_total": "Requests rejected for authentication or authorization.",
}


def _label_key(labels: Mapping[str, str] | None) -> LabelKey:
    if not labels:
        return ()
    return tuple(sorted((str(name), str(value)) for name, value in labels.items()))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(label_key: LabelKey, extra: Mapping[str, str] | None = None) -> str:
    items: list[tuple[str, str]] = list(label_key)
    if extra:
        items.extend((str(name), str(value)) for name, value in extra.items())
    if not items:
        return ""
    rendered = ",".join(f'{name}="{_escape(value)}"' for name, value in items)
    return "{" + rendered + "}"


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    counts: list[int]
    total: int = 0
    total_seconds: float = 0.0

    @classmethod
    def create(cls, buckets: tuple[float, ...]) -> _Histogram:
        # ``counts`` are cumulative: observing a value increments every bucket
        # whose upper bound is at least that value, matching Prometheus semantics.
        return cls(buckets=buckets, counts=[0] * len(buckets))


class MetricsRegistry:
    """Process-local counters and histograms, safe for concurrent recording."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, LabelKey], float] = {}
        self._histograms: dict[tuple[str, LabelKey], _Histogram] = {}
        self._kinds: dict[str, str] = {}

    def increment(
        self,
        name: str,
        labels: Mapping[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        key = (name, _label_key(labels))
        with self._lock:
            self._kinds.setdefault(name, "counter")
            self._counters[key] = self._counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        observed = max(0.0, value)
        key = (name, _label_key(labels))
        with self._lock:
            self._kinds.setdefault(name, "histogram")
            histogram = self._histograms.get(key)
            if histogram is None:
                histogram = _Histogram.create(SECONDS_BUCKETS)
                self._histograms[key] = histogram
            for index, boundary in enumerate(histogram.buckets):
                if observed <= boundary:
                    histogram.counts[index] += 1
            histogram.total += 1
            histogram.total_seconds += observed

    def counter_value(self, name: str, labels: Mapping[str, str] | None = None) -> float:
        with self._lock:
            return self._counters.get((name, _label_key(labels)), 0.0)

    def histogram_count(self, name: str, labels: Mapping[str, str] | None = None) -> int:
        with self._lock:
            histogram = self._histograms.get((name, _label_key(labels)))
            return histogram.total if histogram is not None else 0

    def render(self) -> str:
        with self._lock:
            counters = dict(self._counters)
            histograms = {key: value for key, value in self._histograms.items()}
            kinds = dict(self._kinds)

        lines: list[str] = []
        for name in sorted(kinds):
            lines.append(f"# HELP {name} {_METRIC_HELP.get(name, name)}")
            lines.append(f"# TYPE {name} {kinds[name]}")
            if kinds[name] == "counter":
                for (metric_name, label_key), value in sorted(counters.items()):
                    if metric_name == name:
                        lines.append(f"{name}{_format_labels(label_key)} {_format_number(value)}")
            else:
                for (metric_name, label_key), histogram in sorted(histograms.items()):
                    if metric_name != name:
                        continue
                    for boundary, count in zip(histogram.buckets, histogram.counts, strict=True):
                        le = _format_number(boundary)
                        lines.append(f"{name}_bucket{_format_labels(label_key, {'le': le})} {count}")
                    inf = _format_labels(label_key, {"le": "+Inf"})
                    lines.append(f"{name}_bucket{inf} {histogram.total}")
                    total_seconds = _format_number(histogram.total_seconds)
                    lines.append(f"{name}_sum{_format_labels(label_key)} {total_seconds}")
                    lines.append(f"{name}_count{_format_labels(label_key)} {histogram.total}")
        return "\n".join(lines) + ("\n" if lines else "")

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._kinds.clear()

    # Domain recording helpers: they encode label names once so call sites cannot
    # drift. Each is a thin wrapper over :meth:`increment` / :meth:`observe`.

    def record_http_request(self, *, method: str, route: str, status: int, duration_seconds: float) -> None:
        verb = method.upper()
        self.increment(
            "expense_ai_http_requests_total",
            {"method": verb, "route": route, "status": str(status)},
        )
        self.observe(
            "expense_ai_http_request_duration_seconds",
            duration_seconds,
            {"method": verb, "route": route},
        )

    def record_chat_turn(self, *, outcome: str, duration_seconds: float) -> None:
        self.increment("expense_ai_chat_turns_total", {"outcome": outcome})
        self.observe("expense_ai_chat_turn_duration_seconds", duration_seconds)

    def record_tool_call(self, *, tool: str, outcome: str, duration_seconds: float) -> None:
        self.increment("expense_ai_tool_calls_total", {"tool": tool, "outcome": outcome})
        self.observe("expense_ai_tool_call_duration_seconds", duration_seconds, {"tool": tool})

    def record_model_call(
        self,
        *,
        provider: str,
        node: str,
        outcome: str,
        duration_seconds: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        labels = {"provider": provider, "node": node}
        self.increment("expense_ai_model_calls_total", {**labels, "outcome": outcome})
        self.observe("expense_ai_model_call_duration_seconds", duration_seconds, labels)
        if prompt_tokens:
            self.increment(
                "expense_ai_model_tokens_total",
                {"provider": provider, "kind": "prompt"},
                prompt_tokens,
            )
        if completion_tokens:
            self.increment(
                "expense_ai_model_tokens_total",
                {"provider": provider, "kind": "completion"},
                completion_tokens,
            )

    def record_model_cost(self, *, provider: str, model: str, cost_usd: float) -> None:
        if cost_usd > 0:
            self.increment(
                "expense_ai_model_cost_usd_total",
                {"provider": provider, "model": model},
                cost_usd,
            )

    def record_rate_limit_rejection(self, *, scope: str) -> None:
        self.increment("expense_ai_rate_limit_rejections_total", {"scope": scope})

    def record_auth_denial(self, *, reason: str) -> None:
        self.increment("expense_ai_auth_denials_total", {"reason": reason})


metrics = MetricsRegistry()


def reset_metrics() -> None:
    """Clear the process-wide registry. Intended for tests."""
    metrics.reset()
