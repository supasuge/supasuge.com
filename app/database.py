"""
Database connection configuration for SQLite.

Simplified to use only SQLite3 for easy deployment.
All queries use SQLAlchemy ORM with parameterized statements for security.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

DatabaseType = Literal["sqlite"]

# SQLite database location
BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "instance" / "blog.db"


def get_database_uri(app_root: Path | None = None) -> tuple[str, DatabaseType]:
    """
    Get SQLite database URI.

    Uses DATABASE_URL if provided.
    Otherwise uses Flask-style instance directory.

    Args:
        app_root: Optional application root path. Defaults to BASE_DIR if not provided.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()

    if database_url.startswith("sqlite:"):
        logger.info("Using SQLite database from DATABASE_URL")
        return database_url, "sqlite"

    # Use provided app_root or default to BASE_DIR
    if app_root is None:
        app_root = BASE_DIR

    instance_dir = app_root / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)

    db_path = (app_root / "instance" / "blog.db").resolve()
    instance_dir = db_path.parent
    instance_dir.mkdir(parents=True, exist_ok=True)

    return f"sqlite:///{db_path}", "sqlite"


def get_engine_options(database_type: DatabaseType) -> dict:
    """
    Engine options for SQLite.

    Configured with:
    - Thread-safe operation (check_same_thread=False)
    - Connection timeout handling
    - Connection pooling with pre-ping
    """
    return {
        "connect_args": {
            "check_same_thread": False,
            "timeout": int(os.getenv("SQLITE_TIMEOUT", "20")),
        },
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
