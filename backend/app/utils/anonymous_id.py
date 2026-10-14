"""Anonymous browser identity for primary rate-limit buckets.

The opaque UUID is not an auth credential. Callers pass the request cookie
map and, when they have one, a mutable session cache. Client-supplied values
are accepted only when they are valid UUID strings. Emitting ``Set-Cookie``
belongs to the HTTP adapter; this module does not write cookies itself.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

ANON_COOKIE_NAME = "jev_anon_id"
_SESSION_KEY = "_jev_anon_id"
_COOKIE_WRITTEN_KEY = "_jev_anon_id_cookie_written"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def generate_anonymous_id() -> str:
    """Cryptographically secure anonymous browser id (UUID v4)."""
    return str(uuid.uuid4())


def is_valid_anonymous_id(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(_UUID_RE.match(value.strip()))


def normalize_anonymous_id(value: str | None) -> str | None:
    if not is_valid_anonymous_id(value):
        return None
    assert value is not None
    return str(uuid.UUID(value.strip()))


def ensure_anonymous_id(
    *,
    cookie_name: str = ANON_COOKIE_NAME,
    cookie_max_age_seconds: int = 60 * 60 * 24 * 365,
    secure: bool = False,
    cookies: dict[str, str] | None = None,
    session_state: Any | None = None,
    persist_cookie: bool = True,
) -> str:
    """Return a stable anonymous id.

    Resolution order: session cache → request cookie → new UUID v4.

    ``persist_cookie`` records that the caller should emit the id as a cookie.
    This function does not write ``Set-Cookie`` itself. ``cookie_max_age_seconds``
    and ``secure`` stay in the signature so an HTTP adapter can pass them through
    when it sets the cookie.
    """
    state = session_state
    cookie_map = cookies or {}
    from_cookie = normalize_anonymous_id(cookie_map.get(cookie_name))

    if state is not None:
        cached = normalize_anonymous_id(state.get(_SESSION_KEY))
        if cached:
            if persist_cookie and (
                from_cookie != cached or not state.get(_COOKIE_WRITTEN_KEY)
            ):
                state[_COOKIE_WRITTEN_KEY] = True
            return cached

    if from_cookie:
        if state is not None:
            state[_SESSION_KEY] = from_cookie
            state[_COOKIE_WRITTEN_KEY] = True
        return from_cookie

    new_id = generate_anonymous_id()
    if state is not None:
        state[_SESSION_KEY] = new_id
        if persist_cookie:
            state[_COOKIE_WRITTEN_KEY] = True
    return new_id
