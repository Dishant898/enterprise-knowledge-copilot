from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from enterprise_knowledge_copilot.app_factory import create_app
from enterprise_knowledge_copilot.config import Settings


@pytest.fixture
def valid_settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://user:pass@localhost:5432/app",
        redis_url="redis://:secret@localhost:6379/0",
    )


def test_settings_require_database_and_redis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_request_id_is_propagated(valid_settings: Settings) -> None:
    app = create_app(valid_settings)
    client = TestClient(app)

    response = client.get("/health/live", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-123"


def test_invalid_request_id_is_replaced(valid_settings: Settings) -> None:
    app = create_app(valid_settings)
    client = TestClient(app)

    response = client.get("/health/live", headers={"X-Request-ID": "bad id!"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Request-ID"] != "bad id!"


def test_404_error_response_is_safe(valid_settings: Settings) -> None:
    app = create_app(valid_settings)
    client = TestClient(app)

    response = client.get("/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert "request_id" in body["error"]
    assert body["error"]["message"]


def test_health_live_and_ready_endpoints(valid_settings: Settings) -> None:
    app = create_app(valid_settings)
    client = TestClient(app)

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"


def test_ready_can_fail_when_dependency_is_unavailable(valid_settings: Settings) -> None:
    app = create_app(valid_settings)
    app.state.dependency_checks = lambda: {"database": True, "redis": False}
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["dependencies"]["redis"] is False
