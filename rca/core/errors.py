"""Platform exception hierarchy and FastAPI exception handlers.

All errors returned by the API share one JSON envelope:

    {"error": {"code": "...", "message": "...", "request_id": "..."}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class RCAError(Exception):
    """Base class for all expected platform errors."""

    status_code: int = 500
    code: str = "rca_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(RCAError):
    code = "configuration_error"


class TelemetrySourceError(RCAError):
    status_code = 502
    code = "telemetry_source_error"


class ModuleNotEnabledError(RCAError):
    status_code = 409
    code = "module_not_enabled"


def _error_response(
    request: Request, status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RCAError)
    async def _rca_error(request: Request, exc: RCAError) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log("%s: %s", exc.code, exc.message)
        return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            request, 422, "validation_error", "Request validation failed.", exc.errors()
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(request, exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
        return _error_response(request, 500, "internal_error", "An unexpected error occurred.")
