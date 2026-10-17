"""Optional trace export to a LangSmith-compatible backend.

Tracing is **off by default**, and enabling it is a deliberate privacy decision:
it exports prompts, tool results and model metadata, which for this service means
the user's question and retrieved financial figures. Enable it only for
development, or point ``LANGSMITH_ENDPOINT`` at a self-hosted instance that is
approved for that data. See ``docs/observability.md``.

LangGraph reads its tracing configuration from the environment. This module
translates typed settings into those variables at startup and, when the tracing
library has already been imported, refreshes its cached environment lookups so
the setting takes effect deterministically.
"""

from __future__ import annotations

import logging
import os
import sys

from app.core.config import Settings

logger = logging.getLogger(__name__)

TRACING_ENV = "LANGSMITH_TRACING"
API_KEY_ENV = "LANGSMITH_API_KEY"
PROJECT_ENV = "LANGSMITH_PROJECT"
ENDPOINT_ENV = "LANGSMITH_ENDPOINT"


def configure_tracing(settings: Settings) -> bool:
    """Apply tracing settings to the environment. Returns whether tracing is on."""
    if not settings.langsmith_tracing:
        return False

    api_key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    if not api_key.strip():
        logger.warning("event=tracing_disabled backend=langsmith reason=missing_api_key")
        return False

    os.environ[TRACING_ENV] = "true"
    os.environ[API_KEY_ENV] = api_key
    os.environ[PROJECT_ENV] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ[ENDPOINT_ENV] = settings.langsmith_endpoint

    _refresh_cached_environment()

    logger.warning(
        "event=tracing_enabled backend=langsmith project=%s note=prompts_and_tool_results_are_exported",
        settings.langsmith_project,
    )
    return True


def _refresh_cached_environment() -> None:
    """Best-effort cache reset so newly-set variables are observed.

    The tracing library memoises environment lookups. When it is already loaded
    its caches must be cleared, otherwise a variable set here would be ignored.
    Looking the module up in ``sys.modules`` avoids a static dependency on an
    optional package; if it is not imported yet it will read the environment
    fresh when it is.
    """
    module = sys.modules.get("langsmith.utils")
    if module is None:
        return
    for attribute in ("get_env_var", "get_tracer_project"):
        cached = getattr(module, attribute, None)
        cache_clear = getattr(cached, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()
