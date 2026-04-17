"""Authenticated API for creating markdown posts.

Posts are parsed, converted to HTML, stored in the DB, and the source
markdown is removed from disk (if it was written). The DB is the single
source of truth.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from flask import current_app, jsonify, request
from werkzeug.datastructures import FileStorage

from auth.decorators import require_admin
from blueprints.api import api_bp
from extensions import limiter

logger = logging.getLogger(__name__)


@api_bp.route("/posts", methods=["POST"])
@limiter.limit("30/hour")
@require_admin
def api_create_post():
    """
    Create or update a post from markdown content.

    Accepts either:
      - multipart/form-data with a 'file' field (markdown file upload)
      - application/json with 'content_md' (raw markdown string)

    Common fields (form or JSON):
      - category:  category slug (default: "general")
      - title:     override frontmatter title
      - summary:   override frontmatter summary
      - tags:      comma-separated tag slugs
      - published: "true"/"false" (default: true)

    On success the markdown source is NOT persisted to disk — the DB
    holds the rendered HTML and original markdown. If a file was written
    to a temp location during processing, it is cleaned up.

    Returns:
        201: {"success": true, "post_id": int, "slug": str, "message": str}
        400: {"success": false, "error": str}
        401: redirect to login (handled by @require_admin)
    """
    from services.upload_service import upload_markdown_to_db

    content_type = request.content_type or ""

    if "json" in content_type:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON body"}), 400

        content_md = data.get("content_md", "").strip()
        if not content_md:
            return jsonify({"success": False, "error": "Missing 'content_md'"}), 400

        if len(content_md) > 2 * 1024 * 1024:
            return jsonify({"success": False, "error": "Content too large (max 2MB)"}), 400

        category = data.get("category", "general").strip() or "general"

        overrides = _build_overrides(data)

        buf = io.BytesIO(content_md.encode("utf-8"))
        title_slug = (overrides.get("title") or "post").replace(" ", "-").lower()[:60]
        virtual_file = FileStorage(
            stream=buf,
            filename=f"{title_slug}.md",
            content_type="text/markdown",
        )

        success, msg, post_id = upload_markdown_to_db(
            virtual_file, category, overrides,
        )

    elif "multipart" in content_type:
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        max_size = current_app.config.get("MAX_UPLOAD_SIZE", 2 * 1024 * 1024)
        if request.content_length and request.content_length > max_size:
            return jsonify({"success": False,
                            "error": f"File too large (max {max_size // 1024}KB)"}), 400

        category = request.form.get("category", "general").strip() or "general"
        overrides = _build_overrides(request.form)

        success, msg, post_id = upload_markdown_to_db(
            file, category, overrides,
        )

    else:
        return jsonify({
            "success": False,
            "error": "Content-Type must be application/json or multipart/form-data",
        }), 400

    if not success:
        return jsonify({"success": False, "error": msg}), 400

    from models import Post, db as sa_db
    post = sa_db.session.query(Post).filter_by(id=post_id).one_or_none()
    slug = post.slug if post else ""

    _cleanup_source_file(post)

    return jsonify({
        "success": True,
        "post_id": post_id,
        "slug": slug,
        "message": msg,
    }), 201


def _build_overrides(data) -> dict:
    """Extract frontmatter overrides from form/JSON data."""
    overrides = {}

    title = (data.get("title") or "").strip()
    if title:
        overrides["title"] = title

    summary = (data.get("summary") or "").strip()
    if summary:
        overrides["summary"] = summary

    tags = (data.get("tags") or "").strip()
    if tags:
        overrides["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    published_raw = data.get("published", "true")
    if isinstance(published_raw, bool):
        overrides["published"] = published_raw
    else:
        overrides["published"] = str(published_raw).lower() != "false"

    return overrides


def _cleanup_source_file(post) -> None:
    """Remove the source markdown file from disk if it exists.

    The DB holds the full content (markdown + rendered HTML), so the
    on-disk file is redundant after insertion. In Docker this prevents
    the container filesystem from accumulating stale files.
    """
    if not post or not post.source_path:
        return

    if post.source_path.startswith("upload://"):
        return

    source = Path(post.source_path)
    if source.is_file():
        try:
            source.unlink()
            logger.info("Cleaned up source file: %s", source)
        except OSError as e:
            logger.warning("Failed to remove source file %s: %s", source, e)
