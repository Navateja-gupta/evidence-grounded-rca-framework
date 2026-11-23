import textwrap

import pytest

from rca.core.config import load_platform_config
from rca.core.errors import ConfigurationError


def _write(path, content: str):
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_default_config_loads_with_no_application_config(make_settings):
    config = load_platform_config(make_settings())

    assert config.application.name == "unconfigured-application"
    assert config.telemetry.provider == "opentelemetry"
    assert config.target.services == []  # nothing hardcoded
    assert config.telemetry.metrics.endpoint is None
    assert set(config.modules.enabled_modules()) == {
        "anomaly_detection",
        "root_cause_ranking",
        "rag",
        "llm_diagnosis",
        "nli_verification",
    }


def test_application_yaml_is_deep_merged_over_defaults(tmp_path, make_settings):
    app_yaml = _write(
        tmp_path / "app.yaml",
        """
        application:
          name: sample-app
        target:
          namespaces: [ns-a]
        modules:
          rag:
            enabled: false
        """,
    )
    config = load_platform_config(make_settings(app_config_path=app_yaml))

    assert config.application.name == "sample-app"
    assert config.target.namespaces == ["ns-a"]
    assert config.target.dependency_source == "traces"  # kept from defaults
    assert "rag" not in config.modules.enabled_modules()
    assert "anomaly_detection" in config.modules.enabled_modules()


def test_env_variables_are_interpolated(tmp_path, monkeypatch, make_settings):
    monkeypatch.setenv("RCA_METRICS_ENDPOINT", "http://metrics.example:9090")
    monkeypatch.setenv("RCA_APPLICATION_NAME", "from-env")
    app_yaml = _write(
        tmp_path / "app.yaml",
        """
        telemetry:
          traces:
            endpoint: ${CUSTOM_TRACES_URL:-http://fallback:16686}
        """,
    )
    config = load_platform_config(make_settings(app_config_path=app_yaml))

    assert config.application.name == "from-env"
    assert config.telemetry.metrics.endpoint == "http://metrics.example:9090"
    assert config.telemetry.traces.endpoint == "http://fallback:16686"


def test_missing_required_env_variable_raises(tmp_path, make_settings):
    app_yaml = _write(tmp_path / "app.yaml", "telemetry:\n  logs:\n    endpoint: ${UNSET_VAR_XYZ}\n")
    with pytest.raises(ConfigurationError, match="UNSET_VAR_XYZ"):
        load_platform_config(make_settings(app_config_path=app_yaml))


def test_unknown_keys_are_rejected(tmp_path, make_settings):
    app_yaml = _write(tmp_path / "app.yaml", "telemetry:\n  metrcs:\n    enabled: true\n")
    with pytest.raises(ConfigurationError, match="metrcs"):
        load_platform_config(make_settings(app_config_path=app_yaml))


def test_missing_application_file_raises(tmp_path, make_settings):
    with pytest.raises(ConfigurationError, match="not found"):
        load_platform_config(make_settings(app_config_path=tmp_path / "missing.yaml"))


def test_invalid_yaml_raises(tmp_path, make_settings):
    app_yaml = _write(tmp_path / "app.yaml", "application: [unclosed\n")
    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        load_platform_config(make_settings(app_config_path=app_yaml))


def test_settings_read_from_environment(monkeypatch, make_settings):
    monkeypatch.setenv("RCA_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("RCA_API_PORT", "9000")
    monkeypatch.setenv("RCA_LLM_API_KEY", "super-secret")
    settings = make_settings()

    assert settings.log_level == "DEBUG"
    assert settings.api_port == 9000
    assert settings.llm_api_key.get_secret_value() == "super-secret"
    assert "super-secret" not in repr(settings)
