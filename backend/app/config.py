"""Application configuration loaded from environment variables.

All secrets come from the environment (or a .env file in development).
Nothing secret is hard-coded; production start-up refuses insecure defaults.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET = "change-me-in-production-this-is-not-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BUC_", extra="ignore")

    # --- general -----------------------------------------------------------
    environment: str = Field(default="development", description="development | test | production")
    app_name: str = "BUC Customer Service Center"
    # Public base URL of the deployment, used to build tracking links and LINE Rich Menu URLs.
    public_base_url: str = "http://localhost:5173"
    timezone: str = "Asia/Bangkok"

    # --- security ----------------------------------------------------------
    secret_key: str = INSECURE_SECRET
    session_cookie_name: str = "buc_session"
    csrf_cookie_name: str = "buc_csrf"
    cookie_secure: bool = False
    session_idle_minutes: int = 60
    session_absolute_hours: int = 12
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    password_min_length: int = 10
    # Comma separated list of origins allowed for CORS (empty = same-origin only).
    cors_origins: str = ""

    # --- database ----------------------------------------------------------
    database_url: str = "postgresql+psycopg://buc:buc_dev_password@localhost:5432/buc_service"
    db_pool_size: int = 10

    # --- files -------------------------------------------------------------
    storage_dir: Path = Path("./storage")
    max_upload_mb: int = 10

    # --- rate limiting (per client IP, per process) --------------------------
    rate_limit_submit_per_hour: int = 20
    rate_limit_track_per_minute: int = 30
    rate_limit_login_per_minute: int = 10

    # --- email (SMTP) --------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "BUC Customer Service <no-reply@example.com>"
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 20

    # --- LINE (optional, disabled by default) ---------------------------------
    # LINE Login / LIFF: used only to verify an ID token sent from a LIFF page.
    line_login_channel_id: str = ""
    # LINE Messaging API: push notifications (future, disabled unless token set + setting enabled).
    line_messaging_channel_access_token: str = ""

    # --- ERPNext (future, disabled) ------------------------------------------
    erpnext_base_url: str = ""
    erpnext_api_key: str = ""
    erpnext_api_secret: str = ""

    # --- worker --------------------------------------------------------------
    worker_poll_seconds: int = 5
    worker_batch_size: int = 20

    @field_validator("public_base_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_for_production(self) -> None:
        """Fail fast when a production deployment uses insecure configuration."""
        if not self.is_production:
            return
        problems = []
        if self.secret_key == INSECURE_SECRET or len(self.secret_key) < 32:
            problems.append("BUC_SECRET_KEY must be set to a random value of at least 32 characters")
        if not self.cookie_secure:
            problems.append("BUC_COOKIE_SECURE must be true in production (HTTPS)")
        if not self.public_base_url.startswith("https://"):
            problems.append("BUC_PUBLIC_BASE_URL must use https:// in production")
        if problems:
            raise RuntimeError("Insecure production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
