"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.api.anonymous import anonymous_id_from_request
from app.config.settings import Settings, get_settings
from app.jev.client import JevClient
from app.jev.rate_limit import JevRateLimiter
from app.utils.client_ip import parse_trusted_proxy_cidrs, resolve_client_ip

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_rate_limiter(request: Request) -> JevRateLimiter:
    """Process-wide limiter created once in ``create_app``."""
    limiter = getattr(request.app.state, "jev_rate_limiter", None)
    if isinstance(limiter, JevRateLimiter):
        return limiter
    created = JevRateLimiter(request.app.state.settings)
    request.app.state.jev_rate_limiter = created
    return created


def get_jev_client(request: Request, settings: SettingsDep) -> Iterator[JevClient]:
    """One HTTP client per request, sharing the application rate limiter."""
    client = JevClient(settings, rate_limiter=get_rate_limiter(request))
    try:
        yield client
    finally:
        client.close()


JevClientDep = Annotated[JevClient, Depends(get_jev_client)]


def caller_identity(
    request: Request, settings: Settings
) -> tuple[str | None, str | None]:
    """Anonymous cookie and client IP for the existing Jev rate limiter."""
    peer = request.client.host if request.client else None
    client_ip = resolve_client_ip(
        peer_ip=peer,
        headers={key: value for key, value in request.headers.items()},
        trusted_proxy_cidrs=parse_trusted_proxy_cidrs(settings.trusted_proxy_cidrs),
    )
    return anonymous_id_from_request(request), client_ip
