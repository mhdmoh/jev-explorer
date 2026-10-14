"""Environment-backed application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Validated configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    jev_api_key: str = Field(default="", alias="JEV_API_KEY")
    jev_model: str = Field(default="jev-1.13.0", alias="JEV_MODEL")
    jev_base_url: str = Field(
        default="https://jevtypesafeai.com/api/v1/decide",
        alias="JEV_BASE_URL",
    )
    jev_timeout_seconds: float = Field(default=30.0, alias="JEV_TIMEOUT_SECONDS")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    policy_version: str = Field(default="1.0", alias="POLICY_VERSION")

    # Deterministic policy thresholds
    auto_execute_max_risk: float = Field(default=2.0, alias="AUTO_EXECUTE_MAX_RISK")
    auto_execute_min_safe: float = Field(default=0.90, alias="AUTO_EXECUTE_MIN_SAFE")
    confirm_max_risk: float = Field(default=3.0, alias="CONFIRM_MAX_RISK")
    confirm_min_safe: float = Field(default=0.50, alias="CONFIRM_MIN_SAFE")
    block_min_risk: float = Field(default=4.0, alias="BLOCK_MIN_RISK")

    demo_workspace: Path = Field(
        default=PROJECT_ROOT / "demo" / "workspace",
        alias="DEMO_WORKSPACE",
    )

    # Outbound Jev API rate limits (live calls only; DEMO MODE is unrestricted)
    # Layer 1: per anonymous browser cookie. Layer 2: per public IP (abuse).
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    anonymous_rate_limit_requests: int = Field(
        default=3,
        alias="ANONYMOUS_RATE_LIMIT_REQUESTS",
        ge=1,
    )
    anonymous_rate_limit_window_seconds: int = Field(
        default=18_000,
        alias="ANONYMOUS_RATE_LIMIT_WINDOW_SECONDS",
        ge=1,
    )
    ip_rate_limit_requests: int = Field(
        default=20,
        alias="IP_RATE_LIMIT_REQUESTS",
        ge=1,
    )
    ip_rate_limit_window_seconds: int = Field(
        default=3_600,
        alias="IP_RATE_LIMIT_WINDOW_SECONDS",
        ge=1,
    )
    anonymous_id_cookie_max_age_seconds: int = Field(
        default=60 * 60 * 24 * 365,
        alias="ANONYMOUS_ID_COOKIE_MAX_AGE_SECONDS",
        ge=60,
    )
    # Comma-separated CIDRs whose TCP peers may set X-Real-IP / X-Forwarded-For.
    # Defaults: loopback + Docker bridge (see app.utils.client_ip).
    trusted_proxy_cidrs: str = Field(
        default="127.0.0.0/8,::1/128,172.16.0.0/12",
        alias="TRUSTED_PROXY_CIDRS",
    )

    # Explicit browser origins allowed to call this API. Never "*".
    cors_allow_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ALLOW_ORIGINS",
    )

    @property
    def cookie_secure(self) -> bool:
        """Use Secure cookies outside local development."""
        return self.app_env.strip().lower() not in {"development", "dev", "local", "test"}

    @field_validator("demo_workspace", mode="before")
    @classmethod
    def resolve_workspace(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @field_validator("cors_allow_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ALLOW_ORIGINS must list at least one origin")
        if any(origin == "*" for origin in origins):
            raise ValueError("CORS_ALLOW_ORIGINS must not use a wildcard origin")
        return ",".join(origins)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return level

    @property
    def jev_configured(self) -> bool:
        return bool(self.jev_api_key.strip())

    def require_jev_api_key(self) -> str:
        key = self.jev_api_key.strip()
        if not key:
            raise ConfigError("JEV_API_KEY is not set. Copy .env.example to .env or use DEMO MODE.")
        return key


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
