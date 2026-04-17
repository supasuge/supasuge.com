"""Tests for services/post_service.py."""

import pytest
from services.post_service import (
    get_all_posts,
    get_post_by_id,
    toggle_post_published,
    delete_post,
    save_post_content,
    save_post_metadata,
)
from models import Post, db


class TestGetAllPosts:
    def test_returns_all(self, app, sample_post, unpublished_post):
        with app.app_context():
            posts = get_all_posts(published_only=False)
            slugs = [p.slug for p in posts]
            assert "test-post" in slugs
            assert "draft-post" in slugs

    def test_published_only(self, app, sample_post, unpublished_post):
        with app.app_context():
            posts = get_all_posts(published_only=True)
            slugs = [p.slug for p in posts]
            assert "test-post" in slugs
            assert "draft-post" not in slugs


class TestGetPostById:
    def test_existing_post(self, app, sample_post):
        with app.app_context():
            post = get_post_by_id(sample_post.id)
            assert post is not None
            assert post.slug == "test-post"

    def test_nonexistent_post(self, app):
        with app.app_context():
            assert get_post_by_id(99999) is None


class TestTogglePublished:
    def test_toggle_unpublishes(self, app, sample_post):
        with app.app_context():
            post = toggle_post_published(sample_post.id)
            assert post.published is False

    def test_toggle_publishes(self, app, unpublished_post):
        with app.app_context():
            post = toggle_post_published(unpublished_post.id)
            assert post.published is True

    def test_nonexistent_returns_none(self, app):
        with app.app_context():
            assert toggle_post_published(99999) is None


class TestDeletePost:
    def test_deletes_existing(self, app, sample_post):
        with app.app_context():
            assert delete_post(sample_post.id) is True
            assert get_post_by_id(sample_post.id) is None

    def test_nonexistent_returns_false(self, app):
        with app.app_context():
            assert delete_post(99999) is False


class TestSavePostContent:
    def test_saves_content(self, app, sample_post):
        with app.app_context():
            new_md = "Updated content here"
            post = save_post_content(sample_post.id, new_md)
            assert post is not None
            assert post.content_md == new_md
            assert "<p>" in post.content_html

    def test_nonexistent_returns_none(self, app):
        with app.app_context():
            assert save_post_content(99999, "content") is None

    def test_does_not_require_source_file(self, app, sample_post):
        """save_post_content is DB-only; source file is not modified."""
        import os

        with app.app_context():
            save_post_content(sample_post.id, "DB only update")
            post = get_post_by_id(sample_post.id)
            assert post.content_md == "DB only update"

        # Source file should be untouched (or absent after archival)
        if os.path.exists(sample_post.source_path):
            with open(sample_post.source_path, "r") as f:
                content = f.read()
            assert "DB only update" not in content


class TestSavePostMetadata:
    def test_saves_metadata(self, app, sample_post):
        with app.app_context():
            post = save_post_metadata(sample_post.id, "New Title", "New Summary", "tag1, tag2")
            assert post is not None
            assert post.title == "New Title"
            assert post.summary == "New Summary"
            tag_slugs = [t.slug for t in post.tags]
            assert "tag1" in tag_slugs
            assert "tag2" in tag_slugs

    def test_nonexistent_returns_none(self, app):
        with app.app_context():
            assert save_post_metadata(99999, "Title", "Summary", "tag") is None
