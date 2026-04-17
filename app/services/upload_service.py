"""Markdown upload service — validates and inserts directly into the database.

No files are persisted to disk. The database is the single source of truth.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from content_indexer import markdown_to_safe_html, sha256_text, parse_markdown_string
from content_sync import (
    create_post,
    get_or_create_category,
    get_or_create_tag,
    unique_slug,
)
from models import Post, db
from security import slugify
from services.markdown_ingest import prepare_markdown_for_storage, source_name_to_title

logger = logging.getLogger(__name__)


def validate_markdown_upload(file: FileStorage) -> Tuple[bool, Optional[str]]:
    """Validate an uploaded markdown file (extension, filename length, UTF-8).

    Args:
        file: Werkzeug FileStorage object from the request.

    Returns:
        (is_valid, error_message_or_None)
    """
    if not file or not file.filename:
        return False, "No file uploaded"

    filename = secure_filename(file.filename)
    if not filename:
        return False, "Invalid filename"

    if len(filename) > 255:
        return False, "Filename too long (max 255 characters)"

    allowed_extensions = current_app.config.get("ALLOWED_EXTENSIONS", {".md", ".markdown"})
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        return False, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"

    # Sniff first bytes to reject binary files
    head = file.read(512)
    file.seek(0)
    try:
        head.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return False, "File does not appear to be valid UTF-8 text"

    return True, None


def upload_markdown_to_db(
    file: FileStorage,
    category_slug: str,
    frontmatter_overrides: Optional[dict] = None,
) -> Tuple[bool, str, Optional[int]]:
    """Upload a markdown file directly into the database.

    1. Validates the upload
    2. Reads file content as UTF-8
    3. Parses frontmatter + body
    4. Inserts/updates the Post in the database

    Args:
        file: Werkzeug FileStorage from the upload form.
        category_slug: Target category slug.
        frontmatter_overrides: Optional dict to override parsed frontmatter fields.

    Returns:
        (success, message, post_id_or_None)
    """
    valid, error = validate_markdown_upload(file)
    if not valid:
        return False, error, None

    try:
        raw = file.read().decode("utf-8")
    except UnicodeDecodeError:
        return False, "File is not valid UTF-8", None

    raw = prepare_markdown_for_storage(raw)
    default_title = source_name_to_title(file.filename)

    try:
        parsed = parse_markdown_string(
            raw,
            default_category=category_slug,
            default_title=default_title,
        )
    except Exception as e:
        return False, f"Failed to parse markdown: {e}", None

    title = parsed.title
    summary = parsed.summary
    tags = list(parsed.tags)
    published = parsed.published
    content_md = parsed.content_md
    content_html = parsed.content_html
    content_hash = parsed.content_sha256
    slug = parsed.slug
    upload_name = secure_filename(file.filename or "") or "post.md"
    upload_source = f"upload://{category_slug}/{upload_name}"

    if frontmatter_overrides:
        title = frontmatter_overrides.get("title", title)
        summary = frontmatter_overrides.get("summary", summary)
        published = frontmatter_overrides.get("published", published)
        slug = slugify(frontmatter_overrides.get("slug", slug))
        if "tags" in frontmatter_overrides:
            tags = [slugify(t) for t in frontmatter_overrides["tags"] if t]

    try:
        # Check for existing post with same slug
        existing = db.session.query(Post).filter_by(slug=slug).one_or_none()
        if existing:
            existing.title = title
            existing.summary = summary
            existing.content_md = content_md
            existing.content_html = content_html
            existing.content_sha256 = content_hash
            existing.published = published
            existing.source_path = upload_source
            cat = get_or_create_category(db.session, category_slug)
            existing.category = cat

            existing.tags.clear()
            for tslug in tags:
                tslug = slugify(tslug)
                if tslug:
                    tag, _ = get_or_create_tag(db.session, tslug)
                    existing.tags.append(tag)

            db.session.commit()
            msg = f"Post updated: '{title}' (slug={existing.slug})"
            current_app.logger.info(msg)
            return True, msg, existing.id
        else:
            post = create_post(
                db.session,
                title=title,
                content_md=content_md,
                category_slug=category_slug,
                summary=summary,
                tags=tags,
                published=published,
                slug=slug,
                source_path=upload_source,
            )
            db.session.commit()
            msg = f"Post created: '{title}' (slug={post.slug})"
            current_app.logger.info(msg)
            return True, msg, post.id

    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Failed to upload markdown to DB: %s", e)
        return False, f"Database error: {str(e)}", None


def save_uploaded_markdown(file: FileStorage, category_slug: str) -> Tuple[bool, str]:
    """Backward-compatible wrapper around DB-only uploads."""
    success, msg, _ = upload_markdown_to_db(file, category_slug)
    return success, msg


def delete_markdown_file(path: str) -> Tuple[bool, str]:
    """Delete a markdown file inside CONTENT_DIR, or noop for virtual uploads."""
    if not path:
        return False, "No path provided"

    if path.startswith("upload://"):
        return True, "Virtual upload source removed"

    ext = Path(path).suffix.lower()
    if ext not in {".md", ".markdown"}:
        return False, "Security error: only markdown files can be removed"

    content_dir = current_app.config.get("CONTENT_DIR")
    if content_dir:
        allowed_root = Path(content_dir).resolve()
        target = Path(path).resolve()
        if allowed_root not in target.parents and target != allowed_root:
            return False, "Security error: path outside content directory"
    else:
        target = Path(path).resolve()

    if target.exists():
        try:
            target.unlink()
        except OSError as exc:
            return False, f"Failed to delete file: {exc}"

    return True, "Source markdown removed"
