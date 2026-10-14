"""FastAPI entrypoint for the Jev Explorer API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.anonymous import install_anonymous_identity
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.jev import router as jev_router
from app.config.settings import get_settings
from app.jev.rate_limit import JevRateLimiter
from app.ui import mount_frontend
from app.utils.logging import setup_logging


def create_app(static_dir: Path | None = None) -> FastAPI:
    """Build the API without contacting Jev or requiring an API key."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Jev Explorer",
        version=__version__,
        summary="Safety gateway API for typed Jev decisions.",
    )
    # One limiter for every decision route in this process. Counters reset
    # when the process restarts and are not shared with other workers.
    app.state.settings = settings
    app.state.jev_rate_limiter = JevRateLimiter(settings)
    install_anonymous_identity(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(jev_router)
    mount_frontend(app, static_dir)
    return app


app = create_app()
