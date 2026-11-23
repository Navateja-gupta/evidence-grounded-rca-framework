"""Aggregates all versioned API routers (mounted under Settings.api_prefix)."""

from fastapi import APIRouter

from rca.api.routes import system


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(system.router)
    return router
