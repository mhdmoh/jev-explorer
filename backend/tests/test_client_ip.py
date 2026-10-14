"""Tests for trusted-proxy client IP resolution."""

from __future__ import annotations

from app.utils.client_ip import resolve_client_ip

TRUSTED = ("127.0.0.0/8", "::1/128", "172.16.0.0/12")


def test_uses_x_real_ip_when_peer_is_docker_bridge() -> None:
    ip = resolve_client_ip(
        peer_ip="172.17.0.1",
        headers={
            "X-Real-IP": "203.0.113.50",
            "X-Forwarded-For": "203.0.113.50",
        },
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "203.0.113.50"


def test_uses_x_real_ip_when_peer_is_loopback() -> None:
    ip = resolve_client_ip(
        peer_ip="127.0.0.1",
        headers={"X-Real-IP": "198.51.100.9"},
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "198.51.100.9"


def test_ignores_spoofed_forwarded_headers_from_untrusted_peer() -> None:
    ip = resolve_client_ip(
        peer_ip="203.0.113.99",
        headers={
            "X-Real-IP": "1.2.3.4",
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
        },
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "203.0.113.99"


def test_spoofed_xff_prefix_does_not_bypass_when_proxy_overwrites() -> None:
    # Nginx sets X-Forwarded-For to $remote_addr (single IP). If an older
    # append-style proxy were used, rightmost hop is what the proxy added.
    ip = resolve_client_ip(
        peer_ip="172.17.0.1",
        headers={"X-Forwarded-For": "8.8.8.8, 203.0.113.77"},
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "203.0.113.77"


def test_prefers_x_real_ip_over_xff() -> None:
    ip = resolve_client_ip(
        peer_ip="127.0.0.1",
        headers={
            "X-Real-IP": "203.0.113.1",
            "X-Forwarded-For": "8.8.8.8, 203.0.113.1",
        },
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "203.0.113.1"


def test_different_client_ips_resolve_independently() -> None:
    a = resolve_client_ip(
        peer_ip="172.17.0.1",
        headers={"X-Real-IP": "203.0.113.1"},
        trusted_proxy_cidrs=TRUSTED,
    )
    b = resolve_client_ip(
        peer_ip="172.17.0.1",
        headers={"X-Real-IP": "203.0.113.2"},
        trusted_proxy_cidrs=TRUSTED,
    )
    assert a != b


def test_falls_back_to_peer_when_trusted_but_no_headers() -> None:
    ip = resolve_client_ip(
        peer_ip="172.17.0.1",
        headers={},
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "172.17.0.1"


def test_invalid_x_real_ip_falls_back_to_xff_then_peer() -> None:
    ip = resolve_client_ip(
        peer_ip="172.17.0.1",
        headers={"X-Real-IP": "not-an-ip", "X-Forwarded-For": "203.0.113.8"},
        trusted_proxy_cidrs=TRUSTED,
    )
    assert ip == "203.0.113.8"
