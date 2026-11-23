"""FastAPI application factory.

Run with:  uvicorn rca.main:create_app --factory --reload
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request

from rca import __version__
from rca.api.router import build_api_router
from rca.api.routes import health
from rca.core.config import PlatformConfig, Settings, get_settings, load_platform_config
from rca.core.errors import register_exception_handlers
from rca.core.logging import configure_logging

logger = logging.getLogger("rca")


def create_app(
    settings: Settings | None = None, platform_config: PlatformConfig | None = None
) -> FastAPI:
    """Create the FastAPI app. Arguments allow tests to inject configuration."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    platform_config = platform_config or load_platform_config(settings)

    app = FastAPI(
        title="Evidence-Grounded RCA Platform",
        version=__version__,
        debug=settings.debug,
    )
    app.state.settings = settings
    app.state.platform_config = platform_config

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"request_id": request_id},
        )
        return response

    app.include_router(health.router)  # /health, /ready at root for probes
    app.include_router(build_api_router(), prefix=settings.api_prefix)

    logger.info(
        "RCA platform started (env=%s, application=%s, modules=%s)",
        settings.environment,
        platform_config.application.name,
        platform_config.modules.enabled_modules(),
    )
    return app
