"""Non-sensitive view of the platform's active configuration."""

from fastapi import APIRouter, Depends

from rca import __version__
from rca.api.dependencies import get_app_settings, get_platform_config
from rca.core.config import PlatformConfig, Settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
async def system_info(
    settings: Settings = Depends(get_app_settings),
    config: PlatformConfig = Depends(get_platform_config),
) -> dict:
    telemetry = config.telemetry
    return {
        "version": __version__,
        "environment": settings.environment,
        "application": config.application.model_dump(),
        "telemetry": {
            "provider": telemetry.provider,
            # Only report whether signals are enabled/configured, never endpoints or tokens.
            "signals": {
                name: {"enabled": sig.enabled, "configured": bool(sig.endpoint)}
                for name, sig in (
                    ("metrics", telemetry.metrics),
                    ("logs", telemetry.logs),
                    ("traces", telemetry.traces),
                )
            },
        },
        "modules": config.modules.enabled_modules(),
    }
