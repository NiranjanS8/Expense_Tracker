"""Application entry point: ``uvicorn app.main:app``.

Wires configuration, correlation IDs, request limits, CORS, typed error
handling, the identity resolver and the model provider. No financial domain
logic lives here.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.health import router as health_router
from app.api.v1.router import build_v1_router
from app.core.config import Settings, get_settings
from app.core.correlation import (
    CORRELATION_HEADER,
    get_correlation_id,
    reset_correlation_id,
    resolve_correlation_id,
    set_correlation_id,
)
from app.core.errors import AppError, PayloadTooLargeError, error_payload
from app.core.logging import configure_logging
from app.core.rate_limit import FixedWindowRateLimiter
from app.identity.introspection import IdentityResolver
from app.integrations.expense_tracker_client import ExpenseTrackerClient
from app.integrations.model_provider import ProviderConfigurationError, build_provider
from app.tools import build_tool_registry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    client = ExpenseTrackerClient(
        base_url=settings.expense_tracker_base_url,
        context_path=settings.expense_tracker_context_path,
        timeout_seconds=settings.expense_tracker_timeout_seconds,
        max_retries=settings.expense_tracker_max_retries,
        retry_backoff_seconds=settings.expense_tracker_retry_backoff_seconds,
    )
    app.state.expense_tracker_client = client
    app.state.identity_resolver = IdentityResolver(
        client,
        ttl_seconds=settings.identity_cache_ttl_seconds,
    )
    app.state.tool_registry = build_tool_registry()

    # A misconfigured provider must not prevent startup: readiness reports it.
    try:
        app.state.model_provider = build_provider(settings)
    except ProviderConfigurationError:
        logger.error("event=provider_configuration_invalid provider=%s", settings.llm_provider.value)
        app.state.model_provider = None

    logger.info("event=startup service=%s provider=%s", settings.service_name, settings.llm_provider.value)
    try:
        yield
    finally:
        if app.state.model_provider is not None:
            await app.state.model_provider.aclose()
        await client.aclose()
        logger.info("event=shutdown service=%s", settings.service_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title="Expense Tracker AI",
        description="Read-only AI assistant over the Expense Tracker backend.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.chat_limiter = FixedWindowRateLimiter(
        max_requests=resolved_settings.chat_rate_limit_per_minute,
        window_seconds=60.0,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[CORRELATION_HEADER, "Authorization", "Content-Type"],
        expose_headers=[CORRELATION_HEADER],
    )

    _register_middleware(app)
    _register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(build_v1_router(), prefix=resolved_settings.api_prefix)

    return app


def _register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_and_limits(request: Request, call_next: Any) -> Any:
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        token = set_correlation_id(correlation_id)

        try:
            max_bytes: int = app.state.settings.max_request_bytes
            content_length = request.headers.get("content-length")
            if content_length is not None and content_length.isdigit() and int(content_length) > max_bytes:
                return _json_error(request, PayloadTooLargeError())

            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = correlation_id
            return response
        finally:
            reset_correlation_id(token)


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exception: AppError) -> JSONResponse:
        return _json_error(request, exception)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(request: Request, exception: RequestValidationError) -> JSONResponse:
        details = [
            f"{'.'.join(str(part) for part in error.get('loc', ()))}: {error.get('msg', 'invalid')}"
            for error in exception.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_payload(
                status=status.HTTP_400_BAD_REQUEST,
                code="invalid_request",
                message="The request failed validation.",
                correlation_id=get_correlation_id(),
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exception: Exception) -> JSONResponse:
        logger.error(
            "event=unhandled_exception path=%s error=%s",
            request.url.path,
            type(exception).__name__,
        )
        payload = error_payload(
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected error occurred.",
            correlation_id=get_correlation_id(),
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def _json_error(request: Request, exception: AppError) -> JSONResponse:
    payload = error_payload(
        status=exception.status_code,
        code=exception.code,
        message=exception.message,
        correlation_id=get_correlation_id(),
        details=exception.details,
    )
    response = JSONResponse(status_code=exception.status_code, content=payload)
    for header, value in exception.headers.items():
        response.headers[header] = value
    return response


app = create_app()
