"""Vendor-neutral observability: metrics, cost estimation and optional tracing.

Metrics are authored in-process and rendered in the Prometheus text format; no
metrics server and no extra dependency are required. Tracing is optional and
**off by default** because enabling it exports prompts and tool results to a
third party (see :mod:`app.observability.tracing`).
"""

from app.observability.cost import estimate_cost_usd
from app.observability.metrics import PROMETHEUS_MEDIA_TYPE, metrics, reset_metrics
from app.observability.tracing import configure_tracing

__all__ = [
    "PROMETHEUS_MEDIA_TYPE",
    "configure_tracing",
    "estimate_cost_usd",
    "metrics",
    "reset_metrics",
]
