"""
Application configuration — reads from environment variables / .env file.

Usage
-----
    from app.config import settings

    print(settings.yahoo_client_id)
    print(settings.database_url)

All fields are read from the process environment.  In local development,
a .env file in the project root is loaded automatically by pydantic-settings
(or via python-dotenv as a fallback).
"""

from __future__ import annotations

import os
from functools import lru_cache

# Load .env into os.environ so the fallback path works without pydantic-settings
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on shell environment


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """
        Centralised settings object backed by pydantic-settings.

        Field names correspond directly to environment variable names
        (case-insensitive by pydantic convention).
        """

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

        # ── App ───────────────────────────────────────────────────────────────
        app_env: str = "development"
        port: int = 8000

        # ── Database ──────────────────────────────────────────────────────────
        database_url: str = (
            "postgresql+asyncpg://user:password@localhost:5432/yahoo_pricing_db"
        )

        # ── Redis ─────────────────────────────────────────────────────────────
        redis_url: str = "redis://localhost:6379/0"

        # ── Yahoo! Shopping API ───────────────────────────────────────────────
        yahoo_client_id: str = ""

        # ── LINE Messaging API ────────────────────────────────────────────────
        line_channel_access_token: str = ""

        # ── Security ──────────────────────────────────────────────────────────
        secret_key: str = "changeme-in-production"

        @property
        def is_production(self) -> bool:
            return self.app_env.lower() == "production"

except ImportError:
    # Fallback: plain dataclass backed by os.getenv
    # Install pydantic-settings (pip install pydantic-settings) for full validation.
    class Settings:  # type: ignore[no-redef]
        """Minimal settings class used when pydantic-settings is not installed."""

        app_env: str = os.getenv("APP_ENV", "development")
        port: int = int(os.getenv("PORT", "8000"))
        database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:password@localhost:5432/yahoo_pricing_db",
        )
        redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        yahoo_client_id: str = os.getenv("YAHOO_CLIENT_ID", "")
        line_channel_access_token: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        secret_key: str = os.getenv("SECRET_KEY", "changeme-in-production")

        @property
        def is_production(self) -> bool:
            return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()


# Module-level convenience alias
settings = get_settings()
