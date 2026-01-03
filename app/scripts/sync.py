from __future__ import annotations

import os
import secrets
from pathlib import Path

from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
from app import create_app
from config import Config
from content_sync import sync_content
from models import db
load_dotenv()

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_min_env() -> None:
    # Config() requires these; scripts should be usable without ceremony.
    if not os.getenv("SECRET_KEY"):
        os.environ["SECRET_KEY"] = f"dev-{secrets.token_hex(24)}"

    if not os.getenv("ANALYTICS_SALT"):
        os.environ["ANALYTICS_SALT"] = secrets.token_hex(24)


def main() -> None:
    root = _repo_root()
    os.chdir(root)

    _ensure_min_env()

    app = create_app()
    cfg = Config()

    try:
        with app.app_context():
            res = sync_content(cfg.CONTENT_DIR, db.session)
            print(res)

    except OperationalError as e:
        print("\n[sync] Database connection failed.")
        print(f"[sync] DATABASE_URL={os.getenv('DATABASE_URL')}")
        print("[sync] Fixes:")
        print("  - If using docker: docker compose up -d db && wait for healthy")
        print("  - Ensure creds/db name match compose (.env MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD)")
        print("  - If running on host: ensure db is exposed and reachable at 127.0.0.1:3306")
        print(f"[error]: {e}")
        raise


if __name__ == "__main__":
    main()
