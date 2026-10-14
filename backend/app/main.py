"""FastAPI entrypoint for the AgentGuard API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router
from app.config.settings import get_settings
from app.utils.logging import setup_logging


def create_app() -> FastAPI:
    """Build the API without contacting Jev or requiring an API key."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="AgentGuard",
        version=__version__,
        summary="Safety gateway API for typed Jev decisions.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    app.include_router(health_router)
    return app


app = create_app()
