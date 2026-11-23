import os

import pytest
from fastapi.testclient import TestClient

from rca.core.config import Settings, load_platform_config
from rca.main import create_app

_ENV_VARS = (
    "RCA_APPLICATION_NAME",
    "RCA_METRICS_ENDPOINT",
    "RCA_LOGS_ENDPOINT",
    "RCA_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """Keep the developer's shell environment from leaking into tests."""
    for name in list(os.environ):
        if name.startswith("RCA_") or name in _ENV_VARS:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_settings():
    def _make(**overrides) -> Settings:
        # _env_file=None: ignore any local .env file during tests.
        return Settings(_env_file=None, environment="testing", **overrides)

    return _make


@pytest.fixture
def client(make_settings):
    settings = make_settings()
    app = create_app(settings, load_platform_config(settings))
    with TestClient(app) as test_client:
        yield test_client
