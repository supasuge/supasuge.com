"""Post management service layer.

Thin wrappers around content_sync helpers that use the Flask-SQLAlchemy
session (db.session) so callers don't need to pass it explicitly.
All content lives in the database — no filesystem operations.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from flask import current_app
from models import Post, db
from content_sync import (
    create_post as _create_post,
    create_post_from_markdown as _create_from_md,
    delete_post as _delete_post,
    export_all_posts_as_markdown as _export_all,
    export_post_as_markdown as _export_one,
    get_all_posts as _get_all,
    get_content_stats as _get_stats,
    get_post_by_id as _get_by_id,
    get_post_by_slug as _get_by_slug,
    get_posts_by_category as _get_by_cat,
    get_posts_by_tag as _get_by_tag,
    get_posts_paginated as _get_paginated,
    get_recent_posts as _get_recent,
    search_posts as _search,
    toggle_post_published as _toggle,
    update_post_content as _update_content,
    update_post_metadata as _update_meta,
    bulk_update_published as _bulk_pub,
)
from services.markdown_ingest import prepare_markdown_for_storage


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


def get_all_posts(published_only: bool = False) -> List[Post]:
    """Get all posts, optionally filtered by published status."""
    return _get_all(db.session, published_only=published_only)


def get_post_by_id(post_id: int) -> Optional[Post]:
    """Get a post by its database ID."""
    return _get_by_id(db.session, post_id)


def get_post_by_slug(slug: str, *, published_only: bool = False) -> Optional[Post]:
    """Get a post by its URL slug."""
    return _get_by_slug(db.session, slug, published_only=published_only)


def get_recent_posts(limit: int = 10) -> List[Post]:
    """Get the N most recently updated published posts."""
    return _get_recent(db.session, limit=limit)


def get_posts_by_category(category_slug: str, *, published_only: bool = True) -> List[Post]:
    """Get all posts in a given category."""
    return _get_by_cat(db.session, category_slug, published_only=published_only)


def get_posts_by_tag(tag_slug: str, *, published_only: bool = True) -> List[Post]:
    """Get all posts with a given tag."""
    return _get_by_tag(db.session, tag_slug, published_only=published_only)


def search_posts(query: str, *, published_only: bool = True, limit: int = 50) -> List[Post]:
    """Search posts by title, summary, or content."""
    return _search(db.session, query, published_only=published_only, limit=limit)


def get_posts_paginated(
    *, page: int = 1, per_page: int = 20, published_only: bool = True
) -> tuple[List[Post], int]:
    """Return a page of posts and total count."""
    return _get_paginated(db.session, page=page, per_page=per_page, published_only=published_only)


def get_content_stats() -> Dict[str, int]:
    """Return basic content statistics."""
    return _get_stats(db.session)


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


def create_post(
    *,
    title: str,
    content_md: str,
    category_slug: str = "general",
    summary: str = "",
    tags: Optional[List[str]] = None,
    published: bool = True,
    slug: Optional[str] = None,
) -> Post:
    """Create a new post from individual fields and commit."""
    post = _create_post(
        db.session,
        title=title,
        content_md=content_md,
        category_slug=category_slug,
        summary=summary,
        tags=tags,
        published=published,
        slug=slug,
    )
    db.session.commit()
    current_app.logger.info("Created post %d: %s", post.id, post.title)
    return post


def create_post_from_markdown(
    raw_markdown: str,
    *,
    default_category: str = "general",
    category_override: Optional[str] = None,
    frontmatter_overrides: Optional[dict] = None,
) -> Post:
    """Parse raw markdown (with frontmatter) and insert as a new post."""
    post = _create_from_md(
        db.session,
        raw_markdown,
        default_category=default_category,
        category_override=category_override,
        frontmatter_overrides=frontmatter_overrides,
    )
    current_app.logger.info("Created post from markdown %d: %s", post.id, post.title)
    return post


def save_post_content(post_id: int, content_md: str) -> Optional[Post]:
    """Update a post's markdown content, re-render HTML, and commit."""
    post = _update_content(db.session, post_id, prepare_markdown_for_storage(content_md))
    if post:
        db.session.commit()
        current_app.logger.info("Saved content for post %d: %s", post.id, post.title)
    return post


def save_post_metadata(
    post_id: int,
    title: str,
    summary: str,
    tags_csv: str,
) -> Optional[Post]:
    """Update a post's title, summary, and tags (comma-separated), then commit."""
    tag_slugs = [t.strip() for t in tags_csv.split(",") if t.strip()]
    post = _update_meta(
        db.session,
        post_id,
        title=title,
        summary=summary,
        tags=tag_slugs,
    )
    if post:
        db.session.commit()
        current_app.logger.info("Saved metadata for post %d: %s", post.id, title)
    return post


def toggle_post_published(post_id: int) -> Optional[Post]:
    """Toggle the published status of a post and commit."""
    post = _toggle(db.session, post_id)
    if post:
        db.session.commit()
        current_app.logger.info("Toggled post %d published → %s", post_id, post.published)
    return post


def delete_post(post_id: int) -> bool:
    """Delete a post and commit."""
    deleted = _delete_post(db.session, post_id)
    if deleted:
        db.session.commit()
        current_app.logger.info("Deleted post %d", post_id)
    return deleted


def bulk_update_published(post_ids: List[int], published: bool) -> int:
    """Set published status for multiple posts and commit."""
    count = _bulk_pub(db.session, post_ids, published)
    db.session.commit()
    return count


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_post_as_markdown(post_id: int) -> Optional[str]:
    """Export a single post as a markdown document with frontmatter."""
    return _export_one(db.session, post_id)


def export_all_posts() -> List[tuple[str, str]]:
    """Export all posts as (filename, markdown_content) tuples."""
    return _export_all(db.session)
