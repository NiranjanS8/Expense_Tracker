# syntax=docker/dockerfile:1

# Resolve the locked dependency graph and install the service.
FROM python:3.12-slim-bookworm AS builder

# Pinned uv binary; the version- and Python-combined image tags are not published.
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies are copied and installed first so the layer is reused when only
# application code changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Minimal runtime image: no build tools, no credentials, non-root user.
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app /app

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080

# Liveness only. Readiness additionally requires a configured model provider, so
# it is deliberately not used here: a missing credential must surface as
# not-ready rather than as a restarting container.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
