"""Tag management service layer."""

from __future__ import annotations

from sqlalchemy import func
from models import Tag, Post, db, post_tags
from content_sync import get_or_create_tag


def get_tags_with_counts() -> list[tuple[Tag, int]]:
    """Get all tags with post counts (only tags that have posts)."""
    return (
        db.session.query(Tag, func.count(post_tags.c.post_id).label("post_count"))
        .outerjoin(post_tags)
        .group_by(Tag.id)
        .having(func.count(post_tags.c.post_id) > 0)
        .order_by(Tag.slug.asc())
        .all()
    )


def get_unused_tags() -> list[Tag]:
    """Get tags with zero posts."""
    return (
        db.session.query(Tag)
        .outerjoin(post_tags)
        .group_by(Tag.id)
        .having(func.count(post_tags.c.post_id) == 0)
        .order_by(Tag.slug.asc())
        .all()
    )


def attach_tags_to_post(post_id: int, tag_slugs: list[str]) -> list[Tag]:
    """
    Attach tags to a post, creating new tags if needed.

    Note: Does not commit the session. Caller is responsible for committing.

    Args:
        post_id: The post ID to attach tags to
        tag_slugs: List of tag slugs to attach

    Returns:
        List of Tag objects that were attached
    """
    post = db.session.query(Post).filter_by(id=post_id).one_or_none()
    if not post:
        return []

    post.tags.clear()
    tags = []
    for slug in tag_slugs:
        tag, _ = get_or_create_tag(db.session, slug)
        tags.append(tag)
        post.tags.append(tag)

    return tags
