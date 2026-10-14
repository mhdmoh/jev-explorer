"""Tests for two-layer Jev API rate limiting (anonymous id + public IP)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from app.config.settings import Settings
from app.jev.client import JevClient, JevClientError
from app.jev.rate_limit import JevRateLimiter, RateLimitExceeded


def _settings(**overrides: object) -> Settings:
    base = {
        "_env_file": None,
        "JEV_API_KEY": "test-key",
        "RATE_LIMIT_ENABLED": True,
        "ANONYMOUS_RATE_LIMIT_REQUESTS": 3,
        "ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS": 18_000,
        "IP_RATE_LIMIT_REQUESTS": 20,
        "IP_RATE_LIMIT_WINDOW_SECONDS": 3_600,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_same_browser_allows_three_then_blocks() -> None:
    limiter = JevRateLimiter(_settings())
    anon = "11111111-1111-4111-8111-111111111111"
    ip = "203.0.113.10"
    for _ in range(3):
        limiter.acquire(anonymous_id=anon, client_ip=ip)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.acquire(anonymous_id=anon, client_ip=ip)
    assert exc.value.layer == "anonymous"
    assert exc.value.max_calls == 3
    assert exc.value.window_seconds == 18_000


def test_different_browsers_same_ip_have_independent_quotas() -> None:
    limiter = JevRateLimiter(_settings())
    ip = "203.0.113.10"
    browser_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    browser_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    for _ in range(3):
        limiter.acquire(anonymous_id=browser_a, client_ip=ip)
    with pytest.raises(RateLimitExceeded):
        limiter.acquire(anonymous_id=browser_a, client_ip=ip)
    for _ in range(3):
        limiter.acquire(anonymous_id=browser_b, client_ip=ip)


def test_same_browser_different_ip_keeps_anonymous_quota() -> None:
    limiter = JevRateLimiter(_settings(ANONYMOUS_RATE_LIMIT_REQUESTS=3))
    anon = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    limiter.acquire(anonymous_id=anon, client_ip="203.0.113.1")
    limiter.acquire(anonymous_id=anon, client_ip="203.0.113.2")
    limiter.acquire(anonymous_id=anon, client_ip="198.51.100.9")
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.acquire(anonymous_id=anon, client_ip="203.0.113.3")
    assert exc.value.layer == "anonymous"


def test_ip_abuse_protection_blocks_many_anonymous_ids() -> None:
    limiter = JevRateLimiter(
        _settings(
            ANONYMOUS_RATE_LIMIT_REQUESTS=3,
            IP_RATE_LIMIT_REQUESTS=5,
            IP_RATE_LIMIT_WINDOW_SECONDS=3_600,
        )
    )
    ip = "203.0.113.50"
    for i in range(5):
        anon = f"dddddddd-dddd-4ddd-8ddd-{i:012d}"
        limiter.acquire(anonymous_id=anon, client_ip=ip)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.acquire(
            anonymous_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            client_ip=ip,
        )
    assert exc.value.layer == "ip"
    assert exc.value.max_calls == 5


def test_cookie_persistence_same_anonymous_bucket() -> None:
    limiter = JevRateLimiter(_settings(ANONYMOUS_RATE_LIMIT_REQUESTS=2))
    anon = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    ip = "203.0.113.70"
    limiter.acquire(anonymous_id=anon, client_ip=ip)
    limiter.acquire(anonymous_id=anon, client_ip=ip)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.acquire(anonymous_id=anon, client_ip=ip)
    assert exc.value.layer == "anonymous"


def test_rate_limiter_disabled_never_blocks() -> None:
    limiter = JevRateLimiter(
        _settings(RATE_LIMIT_ENABLED=False, ANONYMOUS_RATE_LIMIT_REQUESTS=1)
    )
    for _ in range(5):
        limiter.acquire(
            anonymous_id="11111111-1111-4111-8111-111111111111",
            client_ip="203.0.113.10",
        )


def test_jev_client_decide_respects_anonymous_limit() -> None:
    settings = _settings(ANONYMOUS_RATE_LIMIT_REQUESTS=2)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"answers": {}})
    )
    http = httpx.Client(transport=transport)
    client = JevClient(settings, client=http)
    anon = "12121212-1212-4121-8121-121212121212"

    client.decide({"model": "x"}, client_ip="203.0.113.10", anonymous_id=anon)
    client.decide({"model": "x"}, client_ip="203.0.113.10", anonymous_id=anon)
    with pytest.raises(JevClientError) as exc:
        client.decide({"model": "x"}, client_ip="203.0.113.10", anonymous_id=anon)
    assert exc.value.status_code == 429
    assert "rate limit" in str(exc.value).lower()


def test_jev_client_skips_http_when_rate_limited() -> None:
    settings = _settings(ANONYMOUS_RATE_LIMIT_REQUESTS=1)
    mock_http = MagicMock(spec=httpx.Client)
    mock_http.post.return_value = httpx.Response(200, json={"ok": True})
    client = JevClient(settings, client=mock_http)
    anon = "13131313-1313-4131-8131-131313131313"

    client.decide({"model": "x"}, client_ip="203.0.113.10", anonymous_id=anon)
    with pytest.raises(JevClientError):
        client.decide({"model": "x"}, client_ip="203.0.113.10", anonymous_id=anon)
    assert mock_http.post.call_count == 1
