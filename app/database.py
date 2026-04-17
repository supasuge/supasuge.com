"""
Database connection configuration for SQLite.

Simplified to use only SQLite3 for easy deployment.
All queries use SQLAlchemy ORM with parameterized statements for security.
"""
from __future__ import annotations
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Session
import logging
import os
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

DatabaseType = Literal["sqlite"]


def get_database_uri(instance_path: Path) -> tuple[str, DatabaseType]:
    """
    Build a SQLite database URI using Flask's instance directory.

    Args:
        instance_path: Flask instance directory path

    Returns:
        (database_uri, database_type)
    """
    instance_path = Path(instance_path).resolve()
    instance_path.mkdir(parents=True, exist_ok=True)

    db_path = instance_path / "blog.db"
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

def get_db_session(db: SQLAlchemy, app: Flask) -> Session:
    with app.app_context().no_autoflush:
        return db.session