"""FastAPI dependencies giving routes access to configuration held on app.state."""

from fastapi import Request

from rca.core.config import PlatformConfig, Settings


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_platform_config(request: Request) -> PlatformConfig:
    return request.app.state.platform_config
