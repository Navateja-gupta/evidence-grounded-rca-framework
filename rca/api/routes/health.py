"""Liveness and readiness endpoints (used by Docker / Kubernetes probes)."""

from fastapi import APIRouter, Depends

from rca import __version__
from rca.api.dependencies import get_platform_config
from rca.core.config import PlatformConfig

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def ready(config: PlatformConfig = Depends(get_platform_config)) -> dict:
    # Later phases will add checks for reachability of configured telemetry sources.
    return {"status": "ready", "application": config.application.name}
