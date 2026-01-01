"""Post management service layer."""

from __future__ import annotations

from typing import Optional
from flask import current_app
from models import Post, Category, Tag, db
from content_sync import sync_content


def get_all_posts(published_only: bool = False) -> list[Post]:
    """
    Get all posts, optionally filtered by published status.

    Args:
        published_only: If True, only return published posts

    Returns:
        List of Post objects ordered by updated_at desc
    """
    query = db.session.query(Post)

    if published_only:
        query = query.filter(Post.published.is_(True))

    return query.order_by(Post.updated_at.desc()).all()


def get_post_by_id(post_id: int) -> Optional[Post]:
    """
    Get a post by ID.

    Args:
        post_id: Database ID of the post

    Returns:
        Post object or None if not found
    """
    return db.session.query(Post).filter_by(id=post_id).one_or_none()


def toggle_post_published(post_id: int) -> Optional[Post]:
    """
    Toggle the published status of a post.

    Args:
        post_id: Database ID of the post

    Returns:
        Updated Post object or None if not found

    Example:
        >>> post = toggle_post_published(1)
        >>> print(f"Published: {post.published}")
    """
    post = get_post_by_id(post_id)
    if not post:
        return None

    post.published = not post.published
    db.session.commit()

    current_app.logger.info(
        f"Toggled post {post_id} published status to {post.published}"
    )

    return post


def delete_post(post_id: int) -> bool:
    """
    Delete a post from the database.

    Note: This does NOT delete the source markdown file.
    Use delete_markdown_file() from upload_service for that.

    Args:
        post_id: Database ID of the post

    Returns:
        True if deleted, False if not found
    """
    post = get_post_by_id(post_id)
    if not post:
        return False

    db.session.delete(post)
    db.session.commit()

    current_app.logger.info(f"Deleted post {post_id}: {post.title}")
    return True


def sync_posts_from_filesystem() -> dict:
    """
    Trigger content sync from filesystem to database.

    Returns:
        Dict with sync results:
            - created: int
            - updated: int
            - deleted: int
            - total_indexed: int

    Example:
        >>> results = sync_posts_from_filesystem()
        >>> print(f"Created: {results['created']}, Updated: {results['updated']}")
    """
    content_dir = current_app.config.get("CONTENT_DIR", "content/articles")
    return sync_content(content_dir, db.session)
