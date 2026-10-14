"""HTTP error translation. Responses never include credentials or tracebacks."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config.settings import ConfigError
from app.jev.client import JevClientError
from app.utils.logging import get_logger

logger = get_logger(__name__)


def error_body(
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def api_error(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=error_body(code, message, details=details),
    )


def redact(message: str, secret: str) -> str:
    cleaned = message
    token = secret.strip()
    if token:
        cleaned = cleaned.replace(token, "[redacted]")
    return cleaned.replace("Bearer ", "")


def map_client_error(exc: JevClientError, *, secret: str) -> HTTPException:
    message = redact(str(exc), secret)
    if exc.code == "timeout":
        return api_error(504, "jev_timeout", "The Jev request timed out.")
    if exc.code == "rate_limited":
        return api_error(429, "jev_rate_limited", message)
    if exc.code == "network":
        return api_error(
            502, "jev_network_error", "The Jev service could not be reached."
        )
    if exc.code == "invalid_response":
        return api_error(
            502,
            "jev_invalid_response",
            "The Jev service returned an unexpected response.",
        )
    status = exc.status_code
    detail = f"The Jev service returned HTTP {status}." if status else message
    return api_error(502, "jev_upstream_error", detail)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error",
                "Request validation failed.",
                details=details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_api_error type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "Internal server error."),
        )


def raise_for_jev(exc: Exception, *, secret: str) -> NoReturn:
    """Translate a Jev failure into an HTTPException. Does not return."""
    if isinstance(exc, ConfigError):
        raise api_error(
            503,
            "jev_not_configured",
            "Jev is not configured. Set JEV_API_KEY on the server.",
        ) from exc
    if isinstance(exc, JevClientError):
        logger.warning(
            "jev_decision_failed code=%s status=%s",
            exc.code,
            exc.status_code,
        )
        raise map_client_error(exc, secret=secret) from exc
    raise exc
