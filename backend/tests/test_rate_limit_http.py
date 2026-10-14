"""HTTP rate limits: shared process state, anonymous cookie, and client IP."""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx
from app.api.deps import get_jev_client
from app.config.settings import Settings, get_settings
from app.jev.client import JevClient
from app.jev.rate_limit import JevRateLimiter, ManualClock
from app.main import create_app
from app.utils.anonymous_id import ANON_COOKIE_NAME
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHOICE_URL = "/api/v1/jev/choice"
SCORE_URL = "/api/v1/jev/score"
NOUL_URL = "/api/v1/jev/noul"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_CHOICE = {
    "state": "Customer was charged twice.",
    "instructions": "Where should this go?",
    "criteria": {"billing": "money", "bug": "broken"},
}
_SCORE = {
    "state": "Nobody replied for 3 days.",
    "instructions": "How urgent is this?",
    "criteria": ["routine", "today", "urgent", "critical"],
}
_NOUL = {
    "state": "Delete the production database.",
    "instructions": "Escalate to a human immediately?",
}


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "JEV_API_KEY": "test-key",
        "APP_ENV": "development",
        "RATE_LIMIT_ENABLED": True,
        "ANONYMOUS_RATE_LIMIT_REQUESTS": 3,
        "ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS": 18_000,
        "IP_RATE_LIMIT_REQUESTS": 20,
        "IP_RATE_LIMIT_WINDOW_SECONDS": 3_600,
        "ANONYMOUS_ID_COOKIE_MAX_AGE_SECONDS": 60 * 60 * 24 * 365,
        "TRUSTED_PROXY_CIDRS": "127.0.0.0/8,::1/128,172.16.0.0/12",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _payload(kind: str) -> dict[str, object]:
    if kind == "choice":
        answer: dict[str, object] = {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.99,
            "probabilities": {"billing": 0.99, "bug": 0.01},
        }
    elif kind == "score":
        answer = {
            "type": "score",
            "score": 2.0,
            "confidence": 1.0,
            "probabilities": {"0": 0.0, "3": 1.0},
        }
    else:
        answer = {"type": "noul", "noul": 0.25}
    return {"model": "jev-1.13.0", "answers": {"result": answer}}


@dataclass
class Harness:
    app: FastAPI
    calls: list[httpx.Request] = field(default_factory=list)
    clock: ManualClock = field(default_factory=ManualClock)


def _harness(**overrides: object) -> Harness:
    clock = ManualClock()
    settings = _settings(**overrides)
    application = create_app()
    application.state.settings = settings
    application.state.jev_rate_limiter = JevRateLimiter(settings, clock=clock)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        body = json.loads(request.content.decode())
        kind = body["questions"]["result"]["type"]
        return httpx.Response(200, json=_payload(kind))

    http = httpx.Client(transport=httpx.MockTransport(handler))

    def client_override() -> JevClient:
        return JevClient(
            settings,
            client=http,
            rate_limiter=application.state.jev_rate_limiter,
        )

    application.dependency_overrides[get_jev_client] = client_override
    application.dependency_overrides[get_settings] = lambda: settings
    return Harness(app=application, calls=calls, clock=clock)


def _client(
    harness: Harness, host: str = "203.0.113.10"
) -> TestClient:
    return TestClient(harness.app, client=(host, 50000))


def _post(
    client: TestClient,
    url: str = CHOICE_URL,
    *,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    body = {CHOICE_URL: _CHOICE, SCORE_URL: _SCORE, NOUL_URL: _NOUL}[url]
    return client.post(url, json=body, cookies=cookies, headers=headers)


def test_anonymous_limit_persists_across_requests_and_endpoints() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=3, IP_RATE_LIMIT_REQUESTS=20)
    client = _client(harness)
    statuses = [
        _post(client, CHOICE_URL).status_code,
        _post(client, SCORE_URL).status_code,
        _post(client, NOUL_URL).status_code,
    ]
    assert statuses == [200, 200, 200]
    blocked = _post(client, CHOICE_URL)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "jev_rate_limited"
    assert len(harness.calls) == 3


def test_separate_apps_do_not_share_limiter_state() -> None:
    first = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=1, IP_RATE_LIMIT_REQUESTS=20)
    second = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=1, IP_RATE_LIMIT_REQUESTS=20)
    with _client(first) as first_client:
        assert _post(first_client).status_code == 200
        assert _post(first_client).status_code == 429
    with _client(second) as second_client:
        assert _post(second_client).status_code == 200


def test_first_response_sets_anonymous_cookie_and_later_requests_keep_it() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=3)
    client = _client(harness)
    first = _post(client)
    assert first.status_code == 200
    issued = first.cookies.get(ANON_COOKIE_NAME)
    assert issued is not None
    assert _UUID_RE.match(issued)
    header = first.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "Path=/api/v1/jev" in header
    assert "SameSite=lax" in header
    assert "Secure" not in header
    assert "Max-Age=31536000" in header

    second = _post(client)
    assert second.status_code == 200
    assert ANON_COOKIE_NAME not in second.headers.get("set-cookie", "")
    assert client.cookies.get(ANON_COOKIE_NAME) == issued


def test_production_and_forwarded_https_set_secure_cookie() -> None:
    production = _harness(APP_ENV="production")
    response = _post(_client(production))
    assert "Secure" in response.headers["set-cookie"]

    local = _harness(APP_ENV="development")
    via_nginx = _post(
        _client(local, host="127.0.0.1"),
        headers={"X-Forwarded-Proto": "https"},
    )
    assert "Secure" in via_nginx.headers["set-cookie"]

    spoofed = _post(
        _client(local, host="203.0.113.40"),
        headers={"X-Forwarded-Proto": "https"},
    )
    assert "Secure" not in spoofed.headers["set-cookie"]


def test_invalid_anonymous_ids_are_replaced() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=3, IP_RATE_LIMIT_REQUESTS=20)
    client = _client(harness)
    for raw in ("not-a-uuid", "a" * 4000, "11111111-1111-0111-8111-111111111111"):
        response = _post(client, cookies={ANON_COOKIE_NAME: raw})
        assert response.status_code == 200
        issued = response.cookies.get(ANON_COOKIE_NAME)
        assert issued is not None
        assert _UUID_RE.match(issued)
        assert issued != raw


def test_rejected_request_does_not_rotate_anonymous_id() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=1, IP_RATE_LIMIT_REQUESTS=20)
    client = _client(harness)
    first = _post(client)
    assert first.status_code == 200
    issued = first.cookies[ANON_COOKIE_NAME]

    blocked = _post(client)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "jev_rate_limited"
    assert ANON_COOKIE_NAME not in blocked.headers.get("set-cookie", "")
    assert client.cookies.get(ANON_COOKIE_NAME) == issued

    again = _post(client)
    assert again.status_code == 429
    assert len(harness.calls) == 1


def test_dropping_cookies_cannot_pass_the_ip_limit() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=1, IP_RATE_LIMIT_REQUESTS=2)
    client = _client(harness, host="203.0.113.77")
    assert _post(client).status_code == 200
    client.cookies.clear()
    assert _post(client).status_code == 200
    client.cookies.clear()
    blocked = _post(client)
    assert blocked.status_code == 429
    assert "network" in blocked.json()["error"]["message"]
    assert len(harness.calls) == 2
    # The 429 still pins one id. Repeating it does not mint a usable new quota.
    pinned = blocked.cookies[ANON_COOKIE_NAME]
    follow = _post(client, cookies={ANON_COOKIE_NAME: pinned})
    assert follow.status_code == 429
    assert ANON_COOKIE_NAME not in follow.headers.get("set-cookie", "")


def test_ip_buckets_are_independent_and_ignore_untrusted_forwarded_headers() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=10, IP_RATE_LIMIT_REQUESTS=1)
    first = _client(harness, host="203.0.113.10")
    opened = _post(
        first,
        headers={"X-Real-IP": "1.2.3.4", "X-Forwarded-For": "1.2.3.4, 8.8.8.8"},
    )
    assert opened.status_code == 200
    spoofed_again = _post(
        first,
        headers={"X-Real-IP": "198.51.100.9", "X-Forwarded-For": "198.51.100.9"},
    )
    assert spoofed_again.status_code == 429

    other = _client(harness, host="203.0.113.11")
    assert _post(other).status_code == 200

    proxied = _client(harness, host="127.0.0.1")
    same_public = _post(proxied, headers={"X-Real-IP": "203.0.113.10"})
    assert same_public.status_code == 429
    fresh_public = _post(proxied, headers={"X-Real-IP": "198.51.100.50"})
    assert fresh_public.status_code == 200


def test_http_window_expiry_follows_the_clock() -> None:
    harness = _harness(
        ANONYMOUS_RATE_LIMIT_REQUESTS=1,
        ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS=10,
        IP_RATE_LIMIT_REQUESTS=20,
        IP_RATE_LIMIT_WINDOW_SECONDS=3600,
    )
    client = _client(harness)
    assert _post(client).status_code == 200
    assert _post(client).status_code == 429
    harness.clock.advance(9)
    assert _post(client).status_code == 429
    harness.clock.advance(2)
    assert _post(client).status_code == 200
    assert len(harness.calls) == 2


def test_rate_limit_disabled_does_not_reject() -> None:
    harness = _harness(
        RATE_LIMIT_ENABLED=False,
        ANONYMOUS_RATE_LIMIT_REQUESTS=1,
        IP_RATE_LIMIT_REQUESTS=1,
    )
    client = _client(harness)
    for _ in range(4):
        assert _post(client).status_code == 200
    assert len(harness.calls) == 4


def test_configured_limits_are_enforced() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=2, IP_RATE_LIMIT_REQUESTS=5)
    client = _client(harness)
    assert _post(client).status_code == 200
    assert _post(client).status_code == 200
    denied = _post(client)
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "jev_rate_limited"
    assert len(harness.calls) == 2


def test_cookie_max_age_is_at_least_the_anonymous_window() -> None:
    harness = _harness(
        ANONYMOUS_ID_COOKIE_MAX_AGE_SECONDS=60,
        ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS=18_000,
    )
    response = _post(_client(harness))
    assert "Max-Age=18000" in response.headers["set-cookie"]


def test_missing_api_key_stays_503_and_does_not_spend_quota() -> None:
    harness = _harness(JEV_API_KEY="", ANONYMOUS_RATE_LIMIT_REQUESTS=1)
    client = _client(harness)
    for _ in range(2):
        response = _post(client)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "jev_not_configured"
    assert harness.calls == []

    harness.app.dependency_overrides[get_jev_client] = lambda: JevClient(
        _settings(JEV_API_KEY="test-key", ANONYMOUS_RATE_LIMIT_REQUESTS=1),
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: (
                    harness.calls.append(request) or httpx.Response(200, json=_payload("choice"))
                )
            )
        ),
        rate_limiter=harness.app.state.jev_rate_limiter,
    )
    allowed = _post(client)
    assert allowed.status_code == 200
    assert len(harness.calls) == 1


def test_concurrent_requests_cannot_exceed_the_limit() -> None:
    harness = _harness(ANONYMOUS_RATE_LIMIT_REQUESTS=5, IP_RATE_LIMIT_REQUESTS=100)
    cookie = "15151515-1515-4151-8151-151515151515"
    barrier = threading.Barrier(12)

    def one() -> int:
        barrier.wait()
        with TestClient(harness.app, client=("203.0.113.10", 50000)) as client:
            response = _post(client, cookies={ANON_COOKIE_NAME: cookie})
            return response.status_code

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(lambda _: one(), range(12)))

    assert statuses.count(200) == 5
    assert statuses.count(429) == 7
    assert len(harness.calls) == 5
