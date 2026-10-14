"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.config.settings import Settings, get_settings
from app.jev.client import JevClient
from app.utils.anonymous_id import ANON_COOKIE_NAME, normalize_anonymous_id
from app.utils.client_ip import parse_trusted_proxy_cidrs, resolve_client_ip

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_jev_client(settings: SettingsDep) -> Iterator[JevClient]:
    client = JevClient(settings)
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
    anonymous_id = normalize_anonymous_id(request.cookies.get(ANON_COOKIE_NAME))
    return anonymous_id, client_ip
