"""Liveness and readiness endpoints.

Liveness is intentionally trivial. Readiness validates the configuration the
service cannot run without (a usable model provider) and is deliberately
lightweight: it does not probe Spring Boot, so a Java restart cannot flap the AI
service's readiness.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response, status

from app.integrations.model_provider import ProviderConfigurationError, resolve_provider_config
from app.observability.metrics import PROMETHEUS_MEDIA_TYPE, metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness(request: Request) -> dict[str, str]:
    return {"status": "alive", "service": request.app.state.settings.service_name}


@router.get("/metrics")
async def metrics_scrape(request: Request) -> Response:
    """Prometheus text exposition, closed unless explicitly enabled.

    Metrics carry no financial data, but the endpoint is still an operational
    surface: leave it disabled and reach it only from a trusted network.
    """
    if not request.app.state.settings.metrics_enabled:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(content=metrics.render(), media_type=PROMETHEUS_MEDIA_TYPE)


@router.get("/health/ready")
async def readiness(request: Request, response: Response) -> dict[str, object]:
    settings = request.app.state.settings
    checks: dict[str, str] = {"expense_tracker": "configured"}

    try:
        config = resolve_provider_config(settings)
        checks["model_provider"] = config.name
    except ProviderConfigurationError as exception:
        logger.warning("event=readiness_failed dependency=model_provider")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": checks, "reason": str(exception)}

    database = getattr(request.app.state, "database", None)
    if database is not None and not await database.ping():
        logger.warning("event=readiness_failed dependency=database")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        checks["database"] = "down"
        return {"status": "not_ready", "checks": checks, "reason": "database unavailable"}
    checks["database"] = "up"

    return {"status": "ready", "checks": checks}
