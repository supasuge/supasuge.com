"""Database-only content management helpers.

All content lives in SQLite. This module provides helper functions for
creating, updating, querying, and exporting posts via SQLAlchemy.
No filesystem operations are performed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from content_indexer import (
    markdown_to_safe_html,
    parse_markdown_string,
    render_post_as_markdown,
    sha256_text,
)
from models import Category, Post, Tag, post_tags
from security import slugify
from services.markdown_ingest import prepare_markdown_for_storage, source_name_to_title

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------


def get_or_create_category(db: Session, slug: str, name: str = "") -> Category:
    """Get an existing category by slug, or create a new one.

    Args:
        db: SQLAlchemy session.
        slug: URL-safe category identifier.
        name: Human-readable name (derived from slug if empty).

    Returns:
        The Category instance (may be new or existing).
    """
    slug = slugify(slug)
    name = (name or "").strip() or slug.replace("-", " ").title()

    cat = db.query(Category).filter_by(slug=slug).one_or_none()
    if cat:
        cat.name = name
        return cat

    cat = Category(slug=slug, name=name)
    db.add(cat)
    return cat


def get_all_categories(db: Session) -> List[Category]:
    """Return all categories ordered by name."""
    return db.query(Category).order_by(Category.name).all()


def get_category_by_slug(db: Session, slug: str) -> Optional[Category]:
    """Look up a single category by slug."""
    return db.query(Category).filter_by(slug=slugify(slug)).one_or_none()


def delete_empty_categories(db: Session) -> int:
    """Delete categories that have no posts. Returns count deleted."""
    empty = (
        db.query(Category)
        .outerjoin(Post)
        .group_by(Category.id)
        .having(func.count(Post.id) == 0)
        .all()
    )
    for cat in empty:
        db.delete(cat)
    db.flush()
    return len(empty)


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------


def get_or_create_tag(db: Session, tag_slug: str) -> tuple[Tag, bool]:
    """Get an existing tag or create a new one.

    Returns:
        (Tag, was_created) tuple.
    """
    tag_slug = slugify(tag_slug)
    pretty = tag_slug.replace("-", " ").title()

    tag = db.query(Tag).filter_by(slug=tag_slug).one_or_none()
    if tag:
        return tag, False

    tag = Tag(slug=tag_slug, name=pretty)
    db.add(tag)
    return tag, True


def get_all_tags(db: Session) -> List[Tag]:
    """Return all tags ordered by name."""
    return db.query(Tag).order_by(Tag.name).all()


def get_tag_by_slug(db: Session, slug: str) -> Optional[Tag]:
    """Look up a single tag by slug."""
    return db.query(Tag).filter_by(slug=slugify(slug)).one_or_none()


def get_tags_with_post_counts(db: Session) -> List[tuple[Tag, int]]:
    """Return tags with their published post counts, ordered by count desc."""
    results = (
        db.query(Tag, func.count(Post.id).label("post_count"))
        .join(post_tags)
        .join(Post)
        .filter(Post.published.is_(True))
        .group_by(Tag.id)
        .order_by(func.count(Post.id).desc())
        .all()
    )
    return [(tag, count) for tag, count in results]


def delete_orphan_tags(db: Session) -> int:
    """Delete tags not associated with any posts. Returns count deleted."""
    orphans = (
        db.query(Tag)
        .outerjoin(post_tags)
        .group_by(Tag.id)
        .having(func.count(post_tags.c.post_id) == 0)
        .all()
    )
    for tag in orphans:
        db.delete(tag)
    db.flush()
    return len(orphans)


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------


def unique_slug(
    db: Session,
    desired: str,
    *,
    exclude_post_id: Optional[int] = None,
) -> str:
    """Generate a unique post slug, appending -2, -3, etc. if needed.

    Args:
        db: SQLAlchemy session.
        desired: The desired slug text.
        exclude_post_id: Exclude this post ID from collision checks (for updates).

    Returns:
        A slug string guaranteed unique among existing posts.
    """
    base = slugify(desired) or "post"

    def _is_taken(slug: str) -> bool:
        q = db.query(Post).filter(Post.slug == slug)
        if exclude_post_id is not None:
            q = q.filter(Post.id != exclude_post_id)
        return q.count() > 0

    if not _is_taken(base):
        return base

    i = 2
    while True:
        candidate = f"{base}-{i}"
        if not _is_taken(candidate):
            return candidate
        i += 1


# ---------------------------------------------------------------------------
# Post CRUD
# ---------------------------------------------------------------------------


def create_post(
    db: Session,
    *,
    title: str,
    content_md: str,
    category_slug: str = "general",
    summary: str = "",
    tags: Optional[List[str]] = None,
    published: bool = True,
    slug: Optional[str] = None,
    source_path: Optional[str] = None,
    subpath: str = "",
) -> Post:
    """Create a new post entirely from in-memory data.

    Args:
        db: SQLAlchemy session.
        title: Post title.
        content_md: Raw markdown body (no frontmatter).
        category_slug: Category slug.
        summary: Short description.
        tags: List of tag slugs.
        published: Whether the post is visible.
        slug: Desired slug (auto-generated from title if omitted).

    Returns:
        The newly created Post (session is flushed but not committed).
    """
    cat = get_or_create_category(db, category_slug)
    resolved_slug = unique_slug(db, slug or title)
    content_html = markdown_to_safe_html(content_md)
    content_hash = sha256_text(content_md)
    normalized_source_path = (source_path or "").strip() or f"memory://{resolved_slug}"

    post = Post(
        slug=resolved_slug,
        title=title,
        summary=summary,
        content_md=content_md,
        content_html=content_html,
        content_sha256=content_hash,
        published=published,
        category=cat,
        source_path=normalized_source_path,
        subpath=(subpath or "").strip(),
    )
    db.add(post)

    if tags:
        with db.no_autoflush:
            for tslug in tags:
                tslug = slugify(tslug)
                if not tslug:
                    continue
                tag, _ = get_or_create_tag(db, tslug)
                post.tags.append(tag)

    db.flush()
    return post


def create_post_from_markdown(
    db: Session,
    raw_markdown: str,
    *,
    default_category: str = "general",
    category_override: Optional[str] = None,
    frontmatter_overrides: Optional[dict] = None,
    source_path: Optional[str] = None,
    subpath: str = "",
) -> Post:
    """Parse a raw markdown string (with frontmatter) and insert as a new post.

    This is the primary way to import content into the database.

    Args:
        db: SQLAlchemy session.
        raw_markdown: Full markdown text with optional YAML frontmatter.
        default_category: Fallback category if none in frontmatter.
        category_override: Force this category regardless of frontmatter.
        frontmatter_overrides: Dict of fields to override after parsing.

    Returns:
        The newly created Post (committed).
    """
    parsed = parse_markdown_string(
        raw_markdown, default_category=default_category
    )

    cat_slug = category_override or parsed.category_slug
    title = parsed.title
    summary = parsed.summary
    tags = list(parsed.tags)
    published = parsed.published

    if frontmatter_overrides:
        title = frontmatter_overrides.get("title", title)
        summary = frontmatter_overrides.get("summary", summary)
        published = frontmatter_overrides.get("published", published)
        if "tags" in frontmatter_overrides:
            tags = [slugify(t) for t in frontmatter_overrides["tags"] if t]
        if "category" in frontmatter_overrides:
            cat_slug = slugify(frontmatter_overrides["category"])

    post = create_post(
        db,
        title=title,
        content_md=parsed.content_md,
        category_slug=cat_slug,
        summary=summary,
        tags=tags,
        published=published,
        slug=parsed.slug,
        source_path=source_path,
        subpath=subpath,
    )
    db.commit()
    return post


def _set_post_tags(
    db: Session,
    post: Post,
    tag_slugs: List[str],
) -> tuple[bool, list[str]]:
    """Replace post tags if needed.

    Returns:
        (changed, new_tag_slugs_created)
    """
    normalized = [slugify(tag) for tag in tag_slugs if slugify(tag)]
    current = sorted(tag.slug for tag in post.tags)
    desired = sorted(dict.fromkeys(normalized))
    if current == desired:
        return False, []

    post.tags.clear()
    new_tags: list[str] = []
    with db.no_autoflush:
        for tslug in desired:
            tag, created = get_or_create_tag(db, tslug)
            post.tags.append(tag)
            if created:
                new_tags.append(tslug)
    return True, new_tags


def _apply_parsed_post(
    db: Session,
    post: Post,
    *,
    parsed,
    source_path: str,
    subpath: str,
) -> tuple[bool, list[str]]:
    """Update an existing post from parsed markdown data."""
    changed = False

    if post.title != parsed.title:
        post.title = parsed.title
        changed = True
    if post.summary != parsed.summary:
        post.summary = parsed.summary
        changed = True
    if post.content_md != parsed.content_md:
        post.content_md = parsed.content_md
        changed = True
    if post.content_html != parsed.content_html:
        post.content_html = parsed.content_html
        changed = True
    if post.content_sha256 != parsed.content_sha256:
        post.content_sha256 = parsed.content_sha256
        changed = True
    if post.published != parsed.published:
        post.published = parsed.published
        changed = True
    if post.source_path != source_path:
        post.source_path = source_path
        changed = True
    normalized_subpath = (subpath or "").strip()
    if (post.subpath or "") != normalized_subpath:
        post.subpath = normalized_subpath
        changed = True

    category = get_or_create_category(db, parsed.category_slug, parsed.category_name)
    if post.category_id != category.id:
        post.category = category
        changed = True

    tags_changed, new_tags = _set_post_tags(db, post, parsed.tags)
    changed = changed or tags_changed
    return changed, new_tags


def _derive_default_category(content_root: Path, markdown_path: Path) -> str:
    """Derive the fallback category from the first path segment."""
    relative = markdown_path.relative_to(content_root)
    if len(relative.parts) > 1:
        return slugify(relative.parts[0]) or "general"
    return "general"


def _is_managed_source(source_path: str | None, content_root: Path) -> bool:
    """Return True if the post source path belongs to the managed content tree."""
    if not source_path:
        return False
    if "://" in source_path:
        return False
    try:
        return content_root in Path(source_path).resolve().parents
    except (OSError, RuntimeError, ValueError):
        return False


def sync_content(content_dir: str | Path, db: Session) -> Dict[str, Any]:
    """Synchronize markdown files from disk into the database.

    The filesystem remains the source of truth for posts under ``content_dir``.
    Existing posts created through uploads or virtual sources are left alone.
    """
    content_root = Path(content_dir).resolve()
    results: Dict[str, Any] = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "unpublished": 0,
        "errors": 0,
        "total_indexed": 0,
        "new_tags": [],
    }

    if not content_root.is_dir():
        logger.warning("Content directory not found, skipping sync: %s", content_root)
        return results

    discovered_paths: set[str] = set()
    new_tag_slugs: set[str] = set()
    known_tag_slugs = {slug for (slug,) in db.query(Tag.slug).all()}

    markdown_files = sorted(content_root.rglob("*.md"))
    for md_file in markdown_files:
        results["total_indexed"] += 1
        source_path = str(md_file.resolve())
        discovered_paths.add(source_path)

        try:
            subpath = md_file.relative_to(content_root).as_posix()
            default_category = _derive_default_category(content_root, md_file)
            raw = prepare_markdown_for_storage(md_file.read_text(encoding="utf-8"))
            parsed = parse_markdown_string(
                raw,
                default_category=default_category,
                default_title=source_name_to_title(md_file.name),
            )

            existing = db.query(Post).filter_by(source_path=source_path).one_or_none()
            if existing is None:
                existing = (
                    db.query(Post)
                    .filter(Post.slug == parsed.slug)
                    .filter(or_(Post.source_path.is_(None), Post.source_path == ""))
                    .one_or_none()
                )

            if existing is None:
                created_tag_slugs = {tag for tag in parsed.tags if tag and tag not in known_tag_slugs}
                post = create_post(
                    db,
                    title=parsed.title,
                    content_md=parsed.content_md,
                    category_slug=parsed.category_slug,
                    summary=parsed.summary,
                    tags=parsed.tags,
                    published=parsed.published,
                    slug=parsed.slug,
                    source_path=source_path,
                    subpath=subpath,
                )
                db.commit()
                known_tag_slugs.update(tag.slug for tag in post.tags)
                new_tag_slugs.update(created_tag_slugs)
                results["created"] += 1
                continue

            changed, created_tags = _apply_parsed_post(
                db,
                existing,
                parsed=parsed,
                source_path=source_path,
                subpath=subpath,
            )
            if changed:
                db.commit()
                known_tag_slugs.update(created_tags)
                new_tag_slugs.update(created_tags)
                results["updated"] += 1
            else:
                results["skipped"] += 1
        except Exception:
            db.rollback()
            logger.exception("Failed to sync markdown file: %s", md_file)
            results["errors"] += 1

    managed_posts = db.query(Post).all()
    unpublished_changed = False
    for post in managed_posts:
        if not _is_managed_source(post.source_path, content_root):
            continue
        if post.source_path in discovered_paths:
            continue
        if post.published:
            post.published = False
            results["unpublished"] += 1
            unpublished_changed = True

    if unpublished_changed:
        db.commit()

    results["new_tags"] = sorted(new_tag_slugs)
    return results


def update_post_content(db: Session, post_id: int, content_md: str) -> Optional[Post]:
    """Re-render and save new markdown content for an existing post.

    Args:
        db: SQLAlchemy session.
        post_id: Database ID.
        content_md: New raw markdown body.

    Returns:
        Updated Post, or None if not found.
    """
    post = db.query(Post).filter_by(id=post_id).one_or_none()
    if not post:
        return None

    post.content_md = content_md
    post.content_html = markdown_to_safe_html(content_md)
    post.content_sha256 = sha256_text(content_md)
    db.flush()
    return post


def update_post_metadata(
    db: Session,
    post_id: int,
    *,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    slug: Optional[str] = None,
    category_slug: Optional[str] = None,
    tags: Optional[List[str]] = None,
    published: Optional[bool] = None,
) -> Optional[Post]:
    """Update metadata fields on an existing post (only provided fields are changed).

    Args:
        db: SQLAlchemy session.
        post_id: Database ID.
        title: New title (or None to keep).
        summary: New summary (or None to keep).
        slug: New slug (or None to keep).
        category_slug: New category (or None to keep).
        tags: New tag list (or None to keep).
        published: New published flag (or None to keep).

    Returns:
        Updated Post, or None if not found.
    """
    post = db.query(Post).filter_by(id=post_id).one_or_none()
    if not post:
        return None

    if title is not None:
        post.title = title
    if summary is not None:
        post.summary = summary
    if slug is not None:
        post.slug = unique_slug(db, slug, exclude_post_id=post.id)
    if category_slug is not None:
        post.category = get_or_create_category(db, category_slug)
    if published is not None:
        post.published = published

    if tags is not None:
        post.tags.clear()
        for tslug in tags:
            tslug = slugify(tslug)
            if not tslug:
                continue
            tag, _ = get_or_create_tag(db, tslug)
            post.tags.append(tag)

    # Recompute hash to reflect any title/summary changes
    post.content_sha256 = sha256_text(post.content_md)
    db.flush()
    return post


def delete_post(db: Session, post_id: int) -> bool:
    """Delete a post by ID.

    Returns:
        True if deleted, False if not found.
    """
    post = db.query(Post).filter_by(id=post_id).one_or_none()
    if not post:
        return False
    db.delete(post)
    db.flush()
    return True


def toggle_post_published(db: Session, post_id: int) -> Optional[Post]:
    """Toggle the published flag on a post.

    Returns:
        Updated Post, or None if not found.
    """
    post = db.query(Post).filter_by(id=post_id).one_or_none()
    if not post:
        return None
    post.published = not post.published
    db.flush()
    return post


# ---------------------------------------------------------------------------
# Post queries
# ---------------------------------------------------------------------------


def get_post_by_id(db: Session, post_id: int) -> Optional[Post]:
    """Fetch a post by its database ID."""
    return db.query(Post).filter_by(id=post_id).one_or_none()


def get_post_by_slug(db: Session, slug: str, *, published_only: bool = False) -> Optional[Post]:
    """Fetch a post by its URL slug."""
    q = db.query(Post).filter(Post.slug == slugify(slug))
    if published_only:
        q = q.filter(Post.published.is_(True))
    return q.one_or_none()


def get_all_posts(
    db: Session,
    *,
    published_only: bool = False,
    order_by_updated: bool = True,
) -> List[Post]:
    """Return all posts with optional filtering and ordering.

    Args:
        db: SQLAlchemy session.
        published_only: If True, exclude unpublished posts.
        order_by_updated: If True, order by updated_at desc (default).

    Returns:
        List of Post objects.
    """
    q = db.query(Post)
    if published_only:
        q = q.filter(Post.published.is_(True))
    if order_by_updated:
        q = q.order_by(Post.updated_at.desc())
    return q.all()


def get_recent_posts(db: Session, limit: int = 10) -> List[Post]:
    """Return the N most recently updated published posts."""
    return (
        db.query(Post)
        .filter(Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .limit(limit)
        .all()
    )


def get_posts_by_category(
    db: Session,
    category_slug: str,
    *,
    published_only: bool = True,
) -> List[Post]:
    """Return all posts in a given category."""
    cat = get_category_by_slug(db, category_slug)
    if not cat:
        return []
    q = db.query(Post).filter(Post.category_id == cat.id)
    if published_only:
        q = q.filter(Post.published.is_(True))
    return q.order_by(Post.updated_at.desc()).all()


def get_posts_by_tag(
    db: Session,
    tag_slug: str,
    *,
    published_only: bool = True,
) -> List[Post]:
    """Return all posts with a given tag."""
    tag = get_tag_by_slug(db, tag_slug)
    if not tag:
        return []
    q = db.query(Post).join(Post.tags).filter(Tag.id == tag.id)
    if published_only:
        q = q.filter(Post.published.is_(True))
    return q.order_by(Post.updated_at.desc()).all()


def search_posts(
    db: Session,
    query: str,
    *,
    published_only: bool = True,
    limit: int = 50,
) -> List[Post]:
    """Search posts by title or content (case-insensitive LIKE).

    Args:
        db: SQLAlchemy session.
        query: Search string.
        published_only: Only search published posts.
        limit: Max results.

    Returns:
        List of matching Post objects.
    """
    pattern = f"%{query}%"
    q = db.query(Post).filter(
        or_(
            Post.title.ilike(pattern),
            Post.content_md.ilike(pattern),
            Post.summary.ilike(pattern),
        )
    )
    if published_only:
        q = q.filter(Post.published.is_(True))
    return q.order_by(Post.updated_at.desc()).limit(limit).all()


def get_posts_paginated(
    db: Session,
    *,
    page: int = 1,
    per_page: int = 20,
    published_only: bool = True,
) -> tuple[List[Post], int]:
    """Return a page of posts and total count.

    Args:
        db: SQLAlchemy session.
        page: 1-based page number.
        per_page: Items per page.
        published_only: Only include published posts.

    Returns:
        (list_of_posts, total_count) tuple.
    """
    q = db.query(Post)
    if published_only:
        q = q.filter(Post.published.is_(True))

    total = q.count()
    posts = (
        q.order_by(Post.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return posts, total


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------


def bulk_update_published(db: Session, post_ids: List[int], published: bool) -> int:
    """Set published status for multiple posts at once.

    Returns:
        Number of rows updated.
    """
    count = (
        db.query(Post)
        .filter(Post.id.in_(post_ids))
        .update({Post.published: published}, synchronize_session="fetch")
    )
    db.flush()
    return count


def bulk_import_markdown(
    db: Session,
    markdown_texts: List[tuple[str, str]],
) -> Dict[str, int]:
    """Import multiple markdown strings into the database.

    Args:
        db: SQLAlchemy session.
        markdown_texts: List of (raw_markdown, category_slug) tuples.

    Returns:
        Dict with counts: created, errors.
    """
    created = 0
    errors = 0

    for raw_md, cat_slug in markdown_texts:
        try:
            create_post_from_markdown(db, raw_md, default_category=cat_slug)
            created += 1
        except Exception as e:
            logger.error("Failed to import markdown: %s", e)
            db.rollback()
            errors += 1

    return {"created": created, "errors": errors}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_post_as_markdown(db: Session, post_id: int) -> Optional[str]:
    """Export a post as a full markdown document (frontmatter + body).

    Returns:
        Markdown string, or None if post not found.
    """
    post = db.query(Post).filter_by(id=post_id).one_or_none()
    if not post:
        return None

    tag_slugs = [t.slug for t in post.tags]
    return render_post_as_markdown(
        title=post.title,
        summary=post.summary,
        tags=tag_slugs,
        published=post.published,
        content_md=post.content_md,
        slug=post.slug,
    )


def export_all_posts_as_markdown(db: Session) -> List[tuple[str, str]]:
    """Export all posts as markdown documents.

    Returns:
        List of (filename, markdown_content) tuples.
    """
    posts = db.query(Post).all()
    results = []
    for post in posts:
        cat_slug = post.category.slug if post.category else "general"
        filename = f"{cat_slug}/{post.slug}.md"
        tag_slugs = [t.slug for t in post.tags]
        md_content = render_post_as_markdown(
            title=post.title,
            summary=post.summary,
            tags=tag_slugs,
            published=post.published,
            content_md=post.content_md,
            slug=post.slug,
        )
        results.append((filename, md_content))
    return results


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_content_stats(db: Session) -> Dict[str, int]:
    """Return basic content statistics.

    Returns:
        Dict with keys: total_posts, published_posts, draft_posts,
        total_categories, total_tags.
    """
    total = db.query(Post).count()
    published = db.query(Post).filter(Post.published.is_(True)).count()
    return {
        "total_posts": total,
        "published_posts": published,
        "draft_posts": total - published,
        "total_categories": db.query(Category).count(),
        "total_tags": db.query(Tag).count(),
    }
