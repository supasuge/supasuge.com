"""Import markdown files from a directory into the database.

Usage:
    uv run python scripts/sync.py [content_dir]

If content_dir is not specified, defaults to app/content/articles.
This is a manual wrapper around the same filesystem sync used automatically
by the application at startup/runtime.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()


def _ensure_min_env() -> None:
    if not os.getenv("SECRET_KEY"):
        os.environ["SECRET_KEY"] = f"dev-{secrets.token_hex(24)}"
    if not os.getenv("ANALYTICS_SALT"):
        os.environ["ANALYTICS_SALT"] = secrets.token_hex(24)


def main() -> None:
    os.chdir(REPO_ROOT)
    _ensure_min_env()

    content_dir = sys.argv[1] if len(sys.argv) > 1 else str(REPO_ROOT / "content" / "articles")
    content_path = Path(content_dir).resolve()

    if not content_path.is_dir():
        print(f"[sync] Directory not found: {content_path}")
        sys.exit(1)

    from app import create_app
    from models import db
    from content_sync import sync_content

    app = create_app()

    with app.app_context():
        results = sync_content(content_path, db.session)

    print(f"[sync] Done: {results}")
    if results["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
