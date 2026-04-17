"""Application bootstrap helpers for schema reconciliation and content sync."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from flask import Flask

from content_sync import sync_content
from models import Post, db

logger = logging.getLogger(__name__)


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Serialize bootstrap work across processes."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def bootstrap_app(app: Flask) -> None:
    """Ensure the database schema exists and content is synced once at startup."""
    if app.config.get("TESTING"):
        return

    lock_path = Path(app.instance_path) / "bootstrap.lock"
    with _file_lock(lock_path):
        with app.app_context():
            _ensure_database_schema(app)
            sync_content_if_needed(app, force=False)


def maybe_sync_content(app: Flask) -> None:
    """Periodically rescan content on live requests."""
    if app.config.get("TESTING") or not app.config.get("AUTO_SYNC_CONTENT", True):
        return

    interval = int(app.config.get("CONTENT_SYNC_INTERVAL_SECONDS", 5))
    state = app.extensions.setdefault("content_sync_runtime", {"last_check": 0.0})
    now = time.monotonic()
    if now - float(state["last_check"]) < interval:
        return

    state["last_check"] = now
    sync_content_if_needed(app, force=False)


def sync_content_if_needed(app: Flask, *, force: bool) -> bool:
    """Sync content from disk into the database when the content tree changed."""
    if not app.config.get("AUTO_SYNC_CONTENT", True):
        return False

    content_root = Path(app.config["CONTENT_DIR"]).resolve()
    if not content_root.is_dir():
        app.logger.info("Content directory not found, skipping automatic sync: %s", content_root)
        return False

    current_signature, file_paths = _scan_content_tree(content_root)
    state_path = Path(app.instance_path) / "content-sync-state.json"
    previous_state = _read_state(state_path)
    with app.app_context():
        database_ready = _database_covers_content_paths(content_root, file_paths)
    if not force and previous_state.get("signature") == current_signature and database_ready:
        return False

    lock_path = Path(app.instance_path) / "content-sync.lock"
    with _file_lock(lock_path):
        current_signature, file_paths = _scan_content_tree(content_root)
        previous_state = _read_state(state_path)
        with app.app_context():
            database_ready = _database_covers_content_paths(content_root, file_paths)
        if not force and previous_state.get("signature") == current_signature and database_ready:
            return False

        with app.app_context():
            results = sync_content(content_root, db.session)

        if results["errors"] == 0:
            _write_state(
                state_path,
                {
                    "signature": current_signature,
                    "synced_at": int(time.time()),
                    "results": results,
                },
            )
        else:
            app.logger.warning("Automatic content sync encountered errors: %s", results)

        app.logger.info("Automatic content sync finished: %s", results)
        return True


def _ensure_database_schema(app: Flask) -> None:
    """Create tables and reconcile known SQLite schema drift."""
    db.create_all()

    if db.engine.url.get_backend_name() != "sqlite":
        return

    with db.engine.begin() as conn:
        columns = {
            row["name"]: row
            for row in conn.exec_driver_sql("PRAGMA table_info(posts)").mappings().all()
        }
        if not columns:
            return

        unique_source_path = False
        index_rows = conn.exec_driver_sql("PRAGMA index_list(posts)").mappings().all()
        for row in index_rows:
            if not row["unique"]:
                continue
            index_name = row["name"]
            info_rows = conn.exec_driver_sql(
                f'PRAGMA index_info("{index_name}")'
            ).mappings().all()
            index_columns = [info["name"] for info in info_rows]
            if index_columns == ["source_path"]:
                unique_source_path = True
                break

        needs_rebuild = (
            "source_path" not in columns
            or int(columns["source_path"]["notnull"]) != 1
            or "subpath" not in columns
            or not unique_source_path
        )
        if needs_rebuild:
            app.logger.info("Reconciling SQLite posts schema")
            _rebuild_posts_table(conn)

        _ensure_posts_indexes(conn)


def _rebuild_posts_table(conn) -> None:
    """Rebuild the posts table to enforce source_path + subpath invariants."""
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS posts__new (
                id INTEGER NOT NULL PRIMARY KEY,
                slug VARCHAR(255) NOT NULL,
                title VARCHAR(512) NOT NULL,
                summary TEXT,
                content_md TEXT NOT NULL,
                content_html TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                source_path VARCHAR(1024) NOT NULL,
                subpath VARCHAR(1024) NOT NULL DEFAULT '',
                content_sha256 VARCHAR(64) NOT NULL,
                published BOOLEAN,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(category_id) REFERENCES categories (id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO posts__new (
                id, slug, title, summary, content_md, content_html,
                category_id, source_path, subpath, content_sha256,
                published, created_at, updated_at
            )
            SELECT
                id,
                slug,
                title,
                summary,
                content_md,
                content_html,
                category_id,
                CASE
                    WHEN source_path IS NULL OR TRIM(source_path) = ''
                    THEN 'legacy://post/' || id
                    ELSE source_path
                END,
                COALESCE(subpath, ''),
                content_sha256,
                published,
                created_at,
                updated_at
            FROM posts
            """
        )
        conn.exec_driver_sql("DROP TABLE posts")
        conn.exec_driver_sql("ALTER TABLE posts__new RENAME TO posts")
    finally:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_posts_indexes(conn) -> None:
    """Restore expected posts indexes after reconciliation."""
    statements = [
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_posts_slug ON posts (slug)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_posts_source_path ON posts (source_path)",
        "CREATE INDEX IF NOT EXISTS ix_posts_category_id ON posts (category_id)",
        "CREATE INDEX IF NOT EXISTS ix_posts_content_sha256 ON posts (content_sha256)",
        "CREATE INDEX IF NOT EXISTS ix_posts_published ON posts (published)",
        "CREATE INDEX IF NOT EXISTS ix_posts_title ON posts (title)",
        "CREATE INDEX IF NOT EXISTS ix_posts_created_at ON posts (created_at)",
    ]
    for statement in statements:
        conn.exec_driver_sql(statement)


def _scan_content_tree(content_root: Path) -> tuple[str, set[str]]:
    """Hash the current markdown tree using path + stat metadata."""
    digest = hashlib.sha256()
    file_paths: set[str] = set()
    for md_file in sorted(content_root.rglob("*.md")):
        stat = md_file.stat()
        file_paths.add(str(md_file.resolve()))
        digest.update(md_file.relative_to(content_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), file_paths


def _database_covers_content_paths(content_root: Path, file_paths: set[str]) -> bool:
    """Return True when every current markdown file already has a DB row."""
    if not file_paths:
        return True

    managed_paths = {
        path
        for (path,) in db.session.query(Post.source_path).all()
        if path and _is_managed_source(path, content_root)
    }
    return file_paths.issubset(managed_paths)


def _is_managed_source(source_path: str, content_root: Path) -> bool:
    """Return True if a source path is inside the managed content directory."""
    if "://" in source_path:
        return False
    try:
        return content_root in Path(source_path).resolve().parents
    except (OSError, RuntimeError, ValueError):
        return False


def _read_state(state_path: Path) -> dict:
    """Read the persisted sync state file."""
    if not state_path.is_file():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Ignoring unreadable content sync state: %s", state_path)
        return {}


def _write_state(state_path: Path, payload: dict) -> None:
    """Atomically persist content sync state."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(state_path)
