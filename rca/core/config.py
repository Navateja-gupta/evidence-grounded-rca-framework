"""Configuration management.

Two layers of configuration are kept deliberately separate:

1. ``Settings`` - runtime / infrastructure settings for the RCA platform itself
   (environment, logging, API bind address, secrets). Loaded from environment
   variables (prefix ``RCA_``) and an optional ``.env`` file.

2. ``PlatformConfig`` - the description of the *target* cloud-native application
   being analysed (telemetry sources, scope, module parameters). Loaded from YAML:
   ``config/default.yaml`` is merged with an optional application-specific YAML
   file whose path is given by ``RCA_APP_CONFIG_PATH``.

YAML values may reference environment variables using ``${VAR}`` or
``${VAR:-default}`` so endpoints and secrets never need to be committed to YAML.

Precedence (lowest -> highest): default.yaml -> application YAML -> env interpolation.
Nothing about any specific application is hardcoded here.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from rca.core.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Runtime settings (environment variables)
# --------------------------------------------------------------------------- #


class Settings(BaseSettings):
    """Platform runtime settings sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_prefix="RCA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api/v1"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    # YAML configuration locations
    config_dir: Path = PROJECT_ROOT / "config"
    app_config_path: Path | None = None  # application-specific YAML (optional)

    # Secrets - never logged or returned by the API.
    llm_api_key: SecretStr | None = None
    telemetry_auth_token: SecretStr | None = None

    @property
    def default_config_path(self) -> Path:
        return self.config_dir / "default.yaml"


# --------------------------------------------------------------------------- #
# Application / platform configuration (YAML)
# --------------------------------------------------------------------------- #


class _StrictModel(BaseModel):
    """Reject unknown keys so typos in YAML are reported, not silently ignored."""

    model_config = ConfigDict(extra="forbid")


class ApplicationInfo(_StrictModel):
    name: str = "unconfigured-application"
    description: str = ""
    environment: str = ""


class TargetScope(_StrictModel):
    """Which part of the target system to analyse.

    Empty lists mean "discover dynamically from telemetry" rather than relying
    on a hardcoded list of services or namespaces.
    """

    namespaces: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    dependency_source: Literal["traces", "static", "none"] = "traces"
    static_dependencies: dict[str, list[str]] = Field(default_factory=dict)


class TelemetrySignal(_StrictModel):
    """One telemetry signal (metrics, logs or traces) and where to query it."""

    enabled: bool = False
    backend: str | None = None  # e.g. the query backend type; resolved by adapters later
    endpoint: str | None = None
    timeout_seconds: float = Field(default=10.0, gt=0)
    options: dict[str, Any] = Field(default_factory=dict)


class OTLPConfig(_StrictModel):
    endpoint: str | None = None
    protocol: Literal["grpc", "http/protobuf"] = "grpc"


class TelemetryConfig(_StrictModel):
    provider: Literal["opentelemetry"] = "opentelemetry"
    otlp: OTLPConfig = Field(default_factory=OTLPConfig)
    metrics: TelemetrySignal = Field(default_factory=TelemetrySignal)
    logs: TelemetrySignal = Field(default_factory=TelemetrySignal)
    traces: TelemetrySignal = Field(default_factory=TelemetrySignal)


class ModuleConfig(_StrictModel):
    """Generic toggle + free-form parameters for an analysis module."""

    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class ModulesConfig(_StrictModel):
    anomaly_detection: ModuleConfig = Field(default_factory=ModuleConfig)
    root_cause_ranking: ModuleConfig = Field(default_factory=ModuleConfig)
    rag: ModuleConfig = Field(default_factory=ModuleConfig)
    llm_diagnosis: ModuleConfig = Field(default_factory=ModuleConfig)
    nli_verification: ModuleConfig = Field(default_factory=ModuleConfig)

    def enabled_modules(self) -> list[str]:
        return [name for name, cfg in self if cfg.enabled]


class PlatformConfig(_StrictModel):
    application: ApplicationInfo = Field(default_factory=ApplicationInfo)
    target: TargetScope = Field(default_factory=TargetScope)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    modules: ModulesConfig = Field(default_factory=ModulesConfig)


# --------------------------------------------------------------------------- #
# YAML loading helpers
# --------------------------------------------------------------------------- #

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _interpolate_env(value: Any) -> Any:
    """Recursively replace ``${VAR}`` / ``${VAR:-default}`` in string values."""
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    if not isinstance(value, str):
        return value

    def _replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        env_value = os.environ.get(name)
        if env_value is not None and env_value != "":
            return env_value
        if default is not None:
            return default
        raise ConfigurationError(
            f"Environment variable '{name}' is referenced in configuration but not set "
            "and no default was provided."
        )

    result = _ENV_PATTERN.sub(_replace, value)
    # A value that was purely an empty substitution becomes None (unset).
    return None if result == "" and _ENV_PATTERN.fullmatch(value) else result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from ``path``; raise ConfigurationError on any problem."""
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"Top-level YAML in {path} must be a mapping.")
    return data


def load_platform_config(settings: Settings) -> PlatformConfig:
    """Build the PlatformConfig from default YAML + optional application YAML."""
    raw: dict[str, Any] = {}
    if settings.default_config_path.is_file():
        raw = load_yaml_file(settings.default_config_path)

    if settings.app_config_path is not None:
        app_path = settings.app_config_path
        if not app_path.is_absolute():
            app_path = (PROJECT_ROOT / app_path).resolve()
        raw = _deep_merge(raw, load_yaml_file(app_path))

    raw = _interpolate_env(raw)
    try:
        return PlatformConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid platform configuration:\n{exc}") from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()
