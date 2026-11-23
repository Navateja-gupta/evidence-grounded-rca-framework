from fastapi import APIRouter
from fastapi.testclient import TestClient

from rca.core.config import load_platform_config
from rca.core.errors import ConfigurationError
from rca.main import create_app


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "X-Request-ID" in response.headers


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "application": "unconfigured-application"}


def test_request_id_is_propagated(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_system_info_does_not_leak_secrets_or_endpoints(monkeypatch, make_settings):
    monkeypatch.setenv("RCA_METRICS_ENDPOINT", "http://internal-metrics:9090")
    settings = make_settings(llm_api_key="super-secret")
    app = create_app(settings, load_platform_config(settings))
    with TestClient(app) as client:
        response = client.get("/api/v1/system/info")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "testing"
    assert body["telemetry"]["signals"]["metrics"] == {"enabled": False, "configured": True}
    assert "super-secret" not in response.text
    assert "internal-metrics" not in response.text


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


def test_platform_errors_use_error_envelope(make_settings):
    settings = make_settings()
    app = create_app(settings, load_platform_config(settings))
    router = APIRouter()

    @router.get("/boom")
    async def boom():
        raise ConfigurationError("bad config")

    @router.get("/crash")
    async def crash():
        raise RuntimeError("unexpected")

    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as client:
        r1 = client.get("/boom")
        r2 = client.get("/crash")

    assert r1.status_code == 500
    assert r1.json()["error"]["code"] == "configuration_error"
    assert r1.json()["error"]["request_id"]
    assert r2.status_code == 500
    assert r2.json()["error"]["code"] == "internal_error"
    assert r2.json()["error"]["message"] == "An unexpected error occurred."  # no internals leaked
