"""Tests for anonymous browser id minting and cookie handling."""

from __future__ import annotations

import uuid

from app.utils.anonymous_id import (
    ANON_COOKIE_NAME,
    ensure_anonymous_id,
    generate_anonymous_id,
    is_valid_anonymous_id,
    normalize_anonymous_id,
)


class _FakeSession(dict):
    pass


def test_generate_anonymous_id_is_uuid_v4() -> None:
    value = generate_anonymous_id()
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert is_valid_anonymous_id(value)


def test_normalize_rejects_non_uuid() -> None:
    assert normalize_anonymous_id("not-a-uuid") is None
    assert normalize_anonymous_id("") is None
    assert normalize_anonymous_id(None) is None


def test_missing_cookie_mints_new_id() -> None:
    session: dict[str, object] = {}
    anon = ensure_anonymous_id(
        cookies={},
        session_state=session,
        persist_cookie=False,
    )
    assert is_valid_anonymous_id(anon)
    assert session["_jev_anon_id"] == anon


def test_existing_cookie_reused() -> None:
    existing = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    session: dict[str, object] = {}
    anon = ensure_anonymous_id(
        cookies={ANON_COOKIE_NAME: existing},
        session_state=session,
        persist_cookie=False,
    )
    assert anon == existing
    assert session["_jev_anon_id"] == existing


def test_invalid_cookie_replaced() -> None:
    session: dict[str, object] = {}
    anon = ensure_anonymous_id(
        cookies={ANON_COOKIE_NAME: "spoofed-identity"},
        session_state=session,
        persist_cookie=False,
    )
    assert is_valid_anonymous_id(anon)
    assert anon != "spoofed-identity"


def test_session_cache_stable_across_calls() -> None:
    session: dict[str, object] = {}
    first = ensure_anonymous_id(
        cookies={},
        session_state=session,
        persist_cookie=False,
    )
    second = ensure_anonymous_id(
        cookies={},
        session_state=session,
        persist_cookie=False,
    )
    assert first == second
