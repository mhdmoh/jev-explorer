"""Issue a stable ``jev_anon_id`` cookie for the Jev decision routes.

The identifier is generated here when the request does not already carry a
valid one. The same value is stored on ``request.state`` before the route
runs, and it is the value the rate limiter charges. A 429 therefore cannot
rotate the identity: the cookie set on that response is the id that was just
consumed, and a request that already presented a valid id is not given a new
one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.config.settings import Settings
from app.utils.anonymous_id import (
    ANON_COOKIE_NAME,
    generate_anonymous_id,
    normalize_anonymous_id,
)
from app.utils.client_ip import is_trusted_proxy, parse_trusted_proxy_cidrs

ANON_COOKIE_PATH = "/api/v1/jev"
_STATE_ANON_ID = "anonymous_id"
_STATE_ISSUE_COOKIE = "issue_anonymous_cookie"


def install_anonymous_identity(app: FastAPI) -> None:
    @app.middleware("http")
    async def anonymous_identity(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not _is_decision_path(request.url.path):
            return await call_next(request)

        existing = normalize_anonymous_id(request.cookies.get(ANON_COOKIE_NAME))
        if existing:
            anon_id = existing
            issue = False
        else:
            anon_id = generate_anonymous_id()
            issue = True
        setattr(request.state, _STATE_ANON_ID, anon_id)
        setattr(request.state, _STATE_ISSUE_COOKIE, issue)

        response = await call_next(request)
        if issue:
            _set_anon_cookie(response, request, anon_id)
        return response


def anonymous_id_from_request(request: Request) -> str | None:
    """Id established by middleware, otherwise a valid cookie, otherwise none."""
    bound = getattr(request.state, _STATE_ANON_ID, None)
    if isinstance(bound, str):
        normalized = normalize_anonymous_id(bound)
        if normalized:
            return normalized
    return normalize_anonymous_id(request.cookies.get(ANON_COOKIE_NAME))


def _is_decision_path(path: str) -> bool:
    return path == ANON_COOKIE_PATH or path.startswith(f"{ANON_COOKIE_PATH}/")


def _set_anon_cookie(response: Response, request: Request, anon_id: str) -> None:
    settings: Settings = request.app.state.settings
    response.set_cookie(
        key=ANON_COOKIE_NAME,
        value=anon_id,
        max_age=_cookie_max_age(settings),
        path=ANON_COOKIE_PATH,
        secure=_cookie_secure(request, settings),
        httponly=True,
        samesite="lax",
    )


def _cookie_max_age(settings: Settings) -> int:
    """Keep the id at least as long as one anonymous rate-limit window.

    The configured max-age defaults to a year, which is longer than the
    18000-second window. A shorter cookie would mint a new identity (and a
    fresh anonymous quota) before the window expired. When the configured
    max-age is already longer, that value is used so the same browser stays
    in one bucket across windows.
    """
    return max(
        settings.anonymous_id_cookie_max_age_seconds,
        settings.anonymous_rate_limit_window_seconds,
    )


def _cookie_secure(request: Request, settings: Settings) -> bool:
    """Secure outside local development, and behind HTTPS-terminating Nginx.

    ``X-Forwarded-Proto`` is honored only when the TCP peer is a trusted
    proxy. A direct client cannot turn the flag on by sending that header.
    """
    if settings.cookie_secure:
        return True
    peer = request.client.host if request.client else None
    if not peer or not is_trusted_proxy(
        peer, parse_trusted_proxy_cidrs(settings.trusted_proxy_cidrs)
    ):
        return False
    forwarded = request.headers.get("x-forwarded-proto", "")
    proto = forwarded.split(",")[0].strip().lower()
    return proto == "https"
