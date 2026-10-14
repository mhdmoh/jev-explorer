"""Two-layer rate limiting for outbound Jev API calls (pyrate-limiter).

Layer 1 — anonymous browser id (primary quota)
Layer 2 — public client IP (abuse protection)
"""

from __future__ import annotations

from pyrate_limiter import (
    AbstractBucket,
    BucketFactory,
    Duration,
    InMemoryBucket,
    Limiter,
    Rate,
    RateItem,
    WallClock,
)

from app.config.settings import Settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a configured Jev API call budget is exhausted."""

    def __init__(
        self,
        message: str,
        *,
        layer: str,
        max_calls: int,
        window_seconds: int,
    ) -> None:
        super().__init__(message)
        self.layer = layer
        self.max_calls = max_calls
        self.window_seconds = window_seconds


class _PerKeyBucketFactory(BucketFactory):
    """One in-memory bucket per acquire() name."""

    def __init__(self, rates: list[Rate]) -> None:
        self._rates = rates
        self._clock = WallClock()
        self._buckets: dict[str, AbstractBucket] = {}

    def wrap_item(self, name: str, weight: int = 1) -> RateItem:
        return RateItem(name=name, timestamp=self._clock.now(), weight=weight)

    def get(self, item: RateItem) -> AbstractBucket:
        bucket = self._buckets.get(item.name)
        if bucket is None:
            bucket = self.create(InMemoryBucket, list(self._rates))
            self._buckets[item.name] = bucket
        return bucket


class JevRateLimiter:
    """Limits live Jev decide calls: anonymous id + public IP abuse cap."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.rate_limit_enabled
        self._anon_max = settings.anonymous_rate_limit_requests
        self._anon_window_s = settings.anonymous_rate_limit_window_seconds
        self._ip_max = settings.ip_rate_limit_requests
        self._ip_window_s = settings.ip_rate_limit_window_seconds

        anon_ms = max(1, int(self._anon_window_s * Duration.SECOND))
        ip_ms = max(1, int(self._ip_window_s * Duration.SECOND))
        self._anon_limiter = Limiter(_PerKeyBucketFactory([Rate(self._anon_max, anon_ms)]))
        self._ip_limiter = Limiter(_PerKeyBucketFactory([Rate(self._ip_max, ip_ms)]))

    def acquire(
        self,
        *,
        anonymous_id: str | None = None,
        client_ip: str | None = None,
    ) -> None:
        """Consume anon + IP permits, or raise RateLimitExceeded (non-blocking).

        Order: IP abuse gate first, then anonymous primary quota. If the anon
        check fails after IP succeeds, the IP permit is still consumed (acceptable
        for abuse protection; normal users rarely hit this path).
        """
        if not self._enabled:
            return

        ip_key = _ip_bucket_key(client_ip)
        if not self._ip_limiter.try_acquire(ip_key, blocking=False):
            logger.warning(
                "jev_rate_limited layer=ip key=%s max=%s window_s=%s",
                ip_key,
                self._ip_max,
                self._ip_window_s,
            )
            raise RateLimitExceeded(
                f"Jev API rate limit exceeded for this network: "
                f"{self._ip_max} call(s) per {_format_window(self._ip_window_s)}. "
                "Try again later.",
                layer="ip",
                max_calls=self._ip_max,
                window_seconds=self._ip_window_s,
            )

        anon_key = _anon_bucket_key(anonymous_id)
        if not self._anon_limiter.try_acquire(anon_key, blocking=False):
            logger.warning(
                "jev_rate_limited layer=anonymous key=%s max=%s window_s=%s",
                anon_key,
                self._anon_max,
                self._anon_window_s,
            )
            raise RateLimitExceeded(
                f"Jev API rate limit exceeded: "
                f"{self._anon_max} call(s) per {_format_window(self._anon_window_s)}. "
                "Try again later.",
                layer="anonymous",
                max_calls=self._anon_max,
                window_seconds=self._anon_window_s,
            )


def _anon_bucket_key(anonymous_id: str | None) -> str:
    anon = (anonymous_id or "").strip() or "unknown"
    return f"anonymous:{anon}"


def _ip_bucket_key(client_ip: str | None) -> str:
    ip = (client_ip or "").strip() or "unknown"
    return f"ip:{ip}"


def _format_window(window_seconds: int) -> str:
    if window_seconds % 3600 == 0:
        hours = window_seconds // 3600
        return f"{hours} hour(s)" if hours != 1 else "1 hour"
    if window_seconds % 60 == 0:
        minutes = window_seconds // 60
        return f"{minutes} minute(s)"
    return f"{window_seconds} second(s)"
