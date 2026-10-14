"""Serve the built Vite frontend from the API process.

The UI is a single page with no client-side router. Only `/`, `/favicon.svg`,
and `/assets` are served from the build. API, health, and docs routes stay
registered first and are never replaced with index.html.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import error_body
from app.config.settings import PROJECT_ROOT

_MISSING = error_body(
    "frontend_not_built",
    "The frontend build is not in the image. Rebuild from the repository root Dockerfile.",
)


def resolve_static_dir(override: Path | None = None) -> Path:
    """Return the compiled frontend directory.

    `override` is for tests. `FRONTEND_STATIC_DIR` is optional and is not
    required in the production env file; the image uses `/app/static`.
    """
    if override is not None:
        return override
    configured = os.environ.get("FRONTEND_STATIC_DIR", "").strip()
    if configured:
        return Path(configured)
    return PROJECT_ROOT / "static"


def mount_frontend(app: FastAPI, static_dir: Path | None = None) -> None:
    """Serve the explorer when index.html and assets are both present."""
    directory = resolve_static_dir(static_dir)
    index = directory / "index.html"
    assets = directory / "assets"
    favicon = directory / "favicon.svg"
    ready = index.is_file() and assets.is_dir()

    if ready:
        app.mount(
            "/assets",
            StaticFiles(directory=assets),
            name="frontend-assets",
        )

    @app.get("/", include_in_schema=False, response_model=None)
    def frontend_index() -> FileResponse | JSONResponse:
        if not ready:
            return JSONResponse(status_code=503, content=_MISSING)
        return FileResponse(index)

    if favicon.is_file():

        @app.get("/favicon.svg", include_in_schema=False)
        def frontend_favicon() -> FileResponse:
            return FileResponse(favicon, media_type="image/svg+xml")
