"""
Database connection resolution with fallback support.

Goal:
- Let the same codebase run in:
  * Docker Compose (MySQL host is usually "db")
  * Local dev on host machine (MySQL host is usually "127.0.0.1" / "localhost")
  * SQLite fallback for quick dev

Key behavior:
- If DATABASE_URL uses host "db" but we're NOT inside Docker, rewrite it to DB_HOST
  (default: 127.0.0.1). This prevents the classic:
    "Can't connect to MySQL server on 'db' (Name or service not known)"
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, DBAPIError

logger = logging.getLogger(__name__)

DatabaseType = Literal["mysql", "sqlite"]

# SQLite database location
BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "instance" / "blog.db"


def _in_docker() -> bool:
    # Common, simple checks. No need to over-engineer it.
    if os.getenv("IN_DOCKER", "").strip() in {"1", "true", "yes", "on"}:
        return True
    if Path("/.dockerenv").exists():
        return True
    # Also common in containerized setups:
    if os.getenv("DOCKER_CONTAINER", "").strip() in {"1", "true", "yes", "on"}:
        return True
    return False


def _rewrite_mysql_host_if_needed(uri: str) -> str:
    """
    If we're running on the host (not inside Docker), and DATABASE_URL points to
    host 'db' (Docker service name), rewrite it to a host-reachable name.

    Defaults:
      DB_HOST=127.0.0.1
      DB_PORT=3306

    This lets you keep a single DATABASE_URL in .env like:
      mysql+pymysql://blogapp:pass@db:3306/blog?charset=utf8mb4

    ...and still run alembic locally.
    """
    if not uri or uri.startswith("sqlite:"):
        return uri

    if _in_docker():
        return uri  # docker DNS will resolve "db"

    # Parse URL safely
    parts = urlsplit(uri)
    host = parts.hostname or ""
    if host != "db":
        return uri

    # Rewrite host and optionally port
    new_host = os.getenv("DB_HOST", "127.0.0.1").strip() or "127.0.0.1"
    new_port = int(os.getenv("DB_PORT", "3306"))

    # Rebuild netloc preserving username/password
    userinfo = ""
    if parts.username:
        userinfo += parts.username
        if parts.password:
            userinfo += f":{parts.password}"
        userinfo += "@"

    netloc = f"{userinfo}{new_host}:{new_port}"

    # Preserve scheme/path/query/fragment exactly
    rewritten = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))

    logger.info("Rewrote DATABASE_URL host db -> %s for non-docker execution", new_host)
    return rewritten


def _test_connection(uri: str, timeout: int = 10) -> bool:
    """
    Test if database connection is viable.
    Handles both MySQL and SQLite safely.
    """
    engine = None
    try:
        uri = (uri or "").strip()
        if not uri:
            return False

        # Normalize docker-service host when running locally
        uri = _rewrite_mysql_host_if_needed(uri)

        # SQLite: connect_args differs, and connect_timeout is not valid
        if uri.startswith("sqlite:"):
            engine = create_engine(uri, pool_pre_ping=True)
        else:
            engine = create_engine(
                uri,
                pool_pre_ping=True,
                connect_args={"connect_timeout": timeout},
            )

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    except (OperationalError, DBAPIError) as e:
        logger.warning("Database connection test failed: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error testing database connection: %s", e)
        return False
    finally:
        if engine is not None:
            engine.dispose()


def _ensure_sqlite_ready() -> tuple[str, DatabaseType]:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{SQLITE_PATH}", "sqlite"


def get_database_uri(
    force_sqlite: bool = False,
    attempt_mysql: bool = True,
) -> tuple[str, DatabaseType]:
    """
    Get database URI with intelligent fallback.

    Strategy:
    1) force_sqlite -> SQLite
    2) If DATABASE_URL set and attempt_mysql -> test it
       - If it contains host 'db' and we are NOT in Docker, rewrite host to DB_HOST
    3) Else SQLite fallback
    """
    if force_sqlite:
        logger.info("Using SQLite database (forced)")
        return _ensure_sqlite_ready()

    database_url = os.getenv("DATABASE_URL", "").strip()

    if database_url and attempt_mysql:
        # Rewrite docker hostname if running locally
        database_url = _rewrite_mysql_host_if_needed(database_url)

        logger.info("Testing database connection...")
        if _test_connection(database_url):
            logger.info("Database connection successful")
            return database_url, "mysql"

        logger.warning("Database connection failed. Falling back to SQLite.")
        logger.warning("DATABASE_URL=%s", database_url)

    logger.info("Using SQLite database (fallback)")
    return _ensure_sqlite_ready()


def get_engine_options(database_type: DatabaseType) -> dict:
    """
    Engine options appropriate for database type.
    """
    if database_type == "mysql":
        # Use DB_* overrides when running locally to avoid "db" hostname assumptions.
        # This does NOT mutate DATABASE_URL; it just affects connect_args pooling.
        return {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "connect_args": {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10"))},
        }

    # sqlite
    return {
        "connect_args": {
            "check_same_thread": False,
            "timeout": int(os.getenv("SQLITE_TIMEOUT", "20")),
        },
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
