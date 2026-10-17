"""Unit tests for optional tracing configuration.

Tracing is a privacy decision: off unless explicitly enabled, never left on
without an API key, and cleaned up here so no other test inherits a live tracer.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.observability import tracing

_ENV_NAMES = (
    tracing.TRACING_ENV,
    tracing.API_KEY_ENV,
    tracing.PROJECT_ENV,
    tracing.ENDPOINT_ENV,
)


def _configure(
    enabled: bool,
    api_key: str | None,
    *,
    project: str = "expense-ai",
    endpoint: str | None = None,
) -> bool:
    settings = Settings(
        _env_file=None,
        langsmith_tracing=enabled,
        langsmith_api_key=SecretStr(api_key) if api_key is not None else None,
        langsmith_project=project,
        langsmith_endpoint=endpoint,
    )
    return tracing.configure_tracing(settings)


@pytest.fixture
def clean_tracing_env() -> Iterator[None]:
    saved = {name: os.environ.get(name) for name in _ENV_NAMES}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        # Keep the tracing library's memoised environment consistent with the
        # restored variables, so a later test never attempts to export a run.
        tracing._refresh_cached_environment()


def test_tracing_defaults_to_off(clean_tracing_env: None) -> None:
    assert _configure(False, None) is False
    assert tracing.TRACING_ENV not in os.environ


def test_tracing_needs_an_api_key(clean_tracing_env: None) -> None:
    assert _configure(True, None) is False
    assert tracing.TRACING_ENV not in os.environ


def test_tracing_sets_the_environment_when_configured(clean_tracing_env: None) -> None:
    enabled = _configure(True, "ls-secret", project="proj", endpoint="https://langsmith.internal")

    assert enabled is True
    assert os.environ[tracing.TRACING_ENV] == "true"
    assert os.environ[tracing.API_KEY_ENV] == "ls-secret"
    assert os.environ[tracing.PROJECT_ENV] == "proj"
    assert os.environ[tracing.ENDPOINT_ENV] == "https://langsmith.internal"
