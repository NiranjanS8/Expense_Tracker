from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import ProviderName, Settings
from app.main import create_app
from tests.conftest import Harness


def test_liveness_is_available_without_authentication(harness: Harness) -> None:
    response = harness.client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "service": "expense-ai"}


def test_readiness_reports_the_fake_provider(harness: Harness) -> None:
    response = harness.client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["model_provider"] == "fake"


def test_readiness_fails_when_provider_credentials_are_missing() -> None:
    settings = Settings(_env_file=None, llm_provider=ProviderName.OPENAI, openai_api_key=None)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
