"""
Application configuration with environment validation.

All configuration is driven by environment variables with secure defaults.
Sensitive values (secrets, passwords) are validated at startup.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, FrozenSet
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Base directory - the app folder
BASE_DIR = Path(__file__).resolve().parent


def _split_csv(v: str) -> List[str]:
    """Split comma-separated string into list, stripping whitespace."""
    return [x.strip() for x in v.split(",") if x.strip()]


def _require_env(name: str) -> str:
    """Get required environment variable or raise with helpful message."""
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def _strip_quotes(s: str) -> str:
    """Remove surrounding quotes from string (common .env file issue)."""
    s = (s or "").strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1].strip()
    return s


def _validate_secret(name: str, value: str, min_length: int = 32) -> str:
    """
    Validate that a secret is not a weak/default value.
    
    Raises RuntimeError with helpful message if validation fails.
    """
    WEAK_DEFAULTS = {
        "change-me-in-production",
        "dev-change-me",
        "your-secret-key-here",
        "replace_with_",
        "change_me",
        "changeme",
        "secret",
        "password",
        "12345",
    }

    value = _strip_quotes(value)
    value_lower = value.lower()
    
    for weak in WEAK_DEFAULTS:
        if weak in value_lower:
            raise RuntimeError(
                f"SECURITY ERROR: {name} contains a weak/default value.\n"
                f"Generate a secure value with:\n"
                f"  ./scripts/gensecrets.sh\n"
                f"Or manually:\n"
                f"  python3 -c 'import secrets; print(secrets.token_hex(32))'\n"
            )

    if len(value) < min_length:
        raise RuntimeError(
            f"SECURITY ERROR: {name} is too short (length: {len(value)}, minimum: {min_length}).\n"
            f"Generate a secure value with:\n"
            f"  ./scripts/gensecrets.sh\n"
        )

    return value


def _require_validated_secret(name: str, min_length: int = 32) -> str:
    """Get and validate a required secret from environment."""
    v = os.getenv(name)
    if not v:
        raise RuntimeError(
            f"Missing required environment variable: {name}\n"
            f"Copy .env.example to .env and set all required values.\n"
        )
    return _validate_secret(name, v, min_length)


def _get_database_url() -> tuple[str, str]:
    """
    Get database URL with fallback support.

    Returns:
        Tuple of (database_uri, database_type)
    """
    from database import get_database_uri

    # In production, require explicit DATABASE_URL
    # In development, allow fallback to SQLite
    force_sqlite = os.getenv("LOCAL_DEV", "0") == "1"
    return get_database_uri(force_sqlite=force_sqlite)


@dataclass(frozen=True)
class Config:
    """
    Application configuration.
    
    All values are loaded from environment variables at startup.
    This is a frozen dataclass to prevent accidental modification.
    """
    
    # Debug/Development flags
    DEBUG: bool = False
    DEVELOPMENT: bool = False
    CSRF_ENABLED: bool = True

    # Site identity
    SITE_NAME: str = os.getenv("SITE_NAME", "Evan Pardon's Portfolio")
    SITE_URL: str = os.getenv("SITE_URL", "https://supasuge.com")

    # Secrets (validated at import time)
    SECRET_KEY: str = _require_validated_secret("SECRET_KEY", min_length=48)
    ANALYTICS_SALT: str = _require_validated_secret("ANALYTICS_SALT", min_length=32)

    # Content directories
    CONTENT_DIR: str = os.getenv("CONTENT_DIR", str(BASE_DIR / "content" / "articles"))
    PUBLIC_DIR: str = os.getenv("PUBLIC_DIR", str(BASE_DIR / "public"))

    # Database (with fallback support)
    _db_uri, _db_type = _get_database_url()
    SQLALCHEMY_DATABASE_URI: str = _db_uri
    DATABASE_TYPE: str = _db_type
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Proxy configuration (behind nginx)
    BEHIND_PROXY: bool = os.getenv("BEHIND_PROXY", "1") == "1"
    PROXY_FIX_X_FOR: int = int(os.getenv("PROXY_FIX_X_FOR", "1"))
    PROXY_FIX_X_PROTO: int = int(os.getenv("PROXY_FIX_X_PROTO", "1"))
    PROXY_FIX_X_HOST: int = int(os.getenv("PROXY_FIX_X_HOST", "1"))

    # Host allowlist (empty = allow all)
    ALLOWED_HOSTS_RAW: str = os.getenv("ALLOWED_HOSTS", "")

    @property
    def ALLOWED_HOSTS(self) -> List[str]:
        """Parse comma-separated allowed hosts."""
        return _split_csv(self.ALLOWED_HOSTS_RAW) if self.ALLOWED_HOSTS_RAW else []

    # Cookie/Session security
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "1") == "1"
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "Lax")
    ENABLE_HSTS: bool = os.getenv("ENABLE_HSTS", "1") == "1"

    # Content Security Policy
    CSP: str = os.getenv(
        "CSP",
        "default-src 'self'; "
        "img-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "base-uri 'self'; "
        "frame-ancestors 'none'",
    )

    # Rate limiting
    RATELIMIT_STORAGE_URL: str = os.getenv("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_DEFAULT: str = os.getenv("RATELIMIT_DEFAULT", "300/hour")

    # Content sync
    AUTO_SYNC_ON_START: bool = os.getenv("AUTO_SYNC_ON_START", "0") == "1"

    # Admin authentication (SSH key)
    ADMIN_SSH_PUBLIC_KEY_PATH: str = os.getenv(
        "ADMIN_SSH_PUBLIC_KEY_PATH", 
        str(BASE_DIR / "keys" / "admin_ssh.pub")
    )
    ADMIN_SSH_PRINCIPAL: str = os.getenv("ADMIN_SSH_PRINCIPAL", "admin")
    ADMIN_SSH_NAMESPACE: str = os.getenv("ADMIN_SSH_NAMESPACE", "supasuge-admin")

    # Admin session timeouts (seconds)
    ADMIN_SESSION_TIMEOUT: int = int(os.getenv("ADMIN_SESSION_TIMEOUT", "28800"))  # 8 hours
    ADMIN_SESSION_RENEWAL: int = int(os.getenv("ADMIN_SESSION_RENEWAL", "3600"))   # 1 hour
    ADMIN_CHALLENGE_EXPIRY: int = int(os.getenv("ADMIN_CHALLENGE_EXPIRY", "300"))  # 5 min

    # Analytics configuration
    ANALYTICS_ENABLED: bool = os.getenv("ANALYTICS_ENABLED", "1") == "1"
    ANALYTICS_RETENTION_DAYS: int = int(os.getenv("ANALYTICS_RETENTION_DAYS", "15"))
    ANALYTICS_RESPECT_DNT: bool = os.getenv("ANALYTICS_RESPECT_DNT", "1") == "1"
    ANALYTICS_SESSION_TIMEOUT: int = int(os.getenv("ANALYTICS_SESSION_TIMEOUT", "1800"))
    GEOIP_DB_PATH: str = os.getenv(
        "GEOIP_DB_PATH", 
        str(BASE_DIR / "data" / "GeoLite2-City.mmdb")
    )

    # Upload limits
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "2097152"))  # 2MB
    
    # Allowed extensions - using frozenset for immutability in frozen dataclass
    @property
    def ALLOWED_EXTENSIONS(self) -> FrozenSet[str]:
        """Allowed file extensions for upload."""
        return frozenset({".md", ".markdown"})

    # Celery (for background tasks if enabled)
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")


def _get_development_database_url() -> tuple[str, str]:
    """
    Get database URL for development (force SQLite).

    Returns:
        Tuple of (database_uri, database_type)
    """
    from database import get_database_uri
    return get_database_uri(force_sqlite=True)


@dataclass(frozen=True)
class DevelopmentConfig(Config):
    """
    Development configuration.

    Differences from base Config:
    - DEBUG mode enabled
    - Uses SQLite database (no MySQL required)
    - Disables cookie security for local testing
    - Disables HSTS
    - Allows weak secrets for convenience
    """

    DEBUG: bool = True
    DEVELOPMENT: bool = True

    # Database: Force SQLite in development
    _db_uri, _db_type = _get_development_database_url()
    SQLALCHEMY_DATABASE_URI: str = _db_uri
    DATABASE_TYPE: str = _db_type

    # Security: Relaxed for local development
    COOKIE_SECURE: bool = False
    ENABLE_HSTS: bool = False

    # Allow insecure secrets in development
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production-DO-NOT-USE-IN-PROD")
    ANALYTICS_SALT: str = os.getenv("ANALYTICS_SALT", "dev-analytics-salt-change-in-production")

    # Local rate limiting (no Redis required)
    RATELIMIT_STORAGE_URL: str = "memory://"


def get_config() -> Config:
    """
    Get appropriate configuration based on environment.

    Returns:
        Config or DevelopmentConfig instance
    """
    if os.getenv("LOCAL_DEV", "0") == "1":
        return DevelopmentConfig()
    return Config()