"""HTTP client for the Jev decide API."""

from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import Settings
from app.jev.rate_limit import JevRateLimiter, RateLimitExceeded
from app.utils.logging import get_logger

logger = get_logger(__name__)


class JevClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JevClient:
    """Thin authenticated client for POST /api/v1/decide."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.Client | None = None,
        rate_limiter: JevRateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._rate_limiter = rate_limiter or JevRateLimiter(settings)

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._settings.jev_timeout_seconds)
        return self._client

    def decide(
        self,
        body: dict[str, Any],
        *,
        run_id: str = "-",
        client_ip: str | None = None,
        anonymous_id: str | None = None,
    ) -> dict[str, Any]:
        api_key = self._settings.require_jev_api_key()
        try:
            self._rate_limiter.acquire(
                anonymous_id=anonymous_id,
                client_ip=client_ip,
            )
        except RateLimitExceeded as exc:
            raise JevClientError(str(exc), status_code=429) from exc

        logger.info("jev_request_started run_id=%s", run_id)

        try:
            response = self._get_client().post(
                self._settings.jev_base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        except httpx.TimeoutException as exc:
            raise JevClientError("Jev request timed out") from exc
        except httpx.HTTPError as exc:
            raise JevClientError(f"Jev HTTP error: {exc}") from exc

        if response.status_code == 401:
            raise JevClientError("Jev authentication failed", status_code=401)
        if response.status_code == 402:
            raise JevClientError("Jev insufficient credits", status_code=402)
        if response.status_code == 403:
            raise JevClientError("Jev account inactive", status_code=403)
        if response.status_code >= 500:
            raise JevClientError(
                f"Jev upstream error (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            detail = _safe_error_detail(response)
            raise JevClientError(
                f"Jev request failed (HTTP {response.status_code}): {detail}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise JevClientError("Jev returned non-JSON response") from exc

        if not isinstance(payload, dict):
            raise JevClientError("Jev response must be a JSON object")

        logger.info("jev_request_completed run_id=%s", run_id)
        return payload


def _safe_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(data, dict):
        for key in ("error", "message", "code", "detail"):
            if key in data:
                return str(data[key])
    return response.text[:200]
