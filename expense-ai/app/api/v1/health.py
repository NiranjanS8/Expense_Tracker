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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness(request: Request) -> dict[str, str]:
    return {"status": "alive", "service": request.app.state.settings.service_name}


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

    return {"status": "ready", "checks": checks}
