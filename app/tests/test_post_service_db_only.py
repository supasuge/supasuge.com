"""Tests for post_service DB-only editing (no filesystem dependency)."""

import pytest


class TestSavePostContentDBOnly:
    """Test that save_post_content works without source file on disk."""

    def test_save_content_updates_db(self, app, sample_post):
        """Saving content updates markdown, html, and hash in DB."""
        with app.app_context():
            from services.post_service import save_post_content, get_post_by_id

            updated = save_post_content(sample_post.id, "# Updated\n\nNew content here")
            assert updated is not None
            assert updated.content_md == "# Updated\n\nNew content here"
            assert "<h1>" in updated.content_html or "<p>" in updated.content_html

            # Verify persisted
            reloaded = get_post_by_id(sample_post.id)
            assert reloaded.content_md == "# Updated\n\nNew content here"

    def test_save_content_without_source_file(self, app, sample_post, tmp_path):
        """Content save works even when source .md file is deleted (archived)."""
        import os

        # Delete the source file to simulate post-archive state
        if os.path.exists(sample_post.source_path):
            os.remove(sample_post.source_path)

        with app.app_context():
            from services.post_service import save_post_content

            updated = save_post_content(sample_post.id, "# Works without file\n\nYes it does")
            assert updated is not None
            assert updated.content_md == "# Works without file\n\nYes it does"

    def test_save_content_nonexistent_post(self, app):
        """Returns None for nonexistent post ID."""
        with app.app_context():
            from services.post_service import save_post_content

            result = save_post_content(99999, "doesn't matter")
            assert result is None

    def test_save_content_updates_hash(self, app, sample_post):
        """Content hash changes when content changes."""
        with app.app_context():
            from services.post_service import save_post_content, get_post_by_id

            original = get_post_by_id(sample_post.id)
            original_hash = original.content_sha256

            save_post_content(sample_post.id, "completely different content")

            updated = get_post_by_id(sample_post.id)
            assert updated.content_sha256 != original_hash


class TestSavePostMetadataDBOnly:
    """Test that save_post_metadata works without source file on disk."""

    def test_save_metadata_updates_db(self, app, sample_post):
        """Saving metadata updates title, summary, and tags in DB."""
        with app.app_context():
            from services.post_service import save_post_metadata, get_post_by_id

            updated = save_post_metadata(
                sample_post.id, "New Title", "New summary", "python, flask"
            )
            assert updated is not None
            assert updated.title == "New Title"
            assert updated.summary == "New summary"

            tag_slugs = [t.slug for t in updated.tags]
            assert "python" in tag_slugs
            assert "flask" in tag_slugs

    def test_save_metadata_without_source_file(self, app, sample_post):
        """Metadata save works even when source .md file is deleted."""
        import os

        if os.path.exists(sample_post.source_path):
            os.remove(sample_post.source_path)

        with app.app_context():
            from services.post_service import save_post_metadata

            updated = save_post_metadata(
                sample_post.id, "Still Works", "Without file", "test"
            )
            assert updated is not None
            assert updated.title == "Still Works"

    def test_save_metadata_nonexistent_post(self, app):
        """Returns None for nonexistent post ID."""
        with app.app_context():
            from services.post_service import save_post_metadata

            result = save_post_metadata(99999, "t", "s", "tags")
            assert result is None

    def test_save_metadata_clears_old_tags(self, app, sample_post):
        """Updating tags replaces old tags completely."""
        with app.app_context():
            from services.post_service import save_post_metadata, get_post_by_id

            # First update: set tags to "alpha, beta"
            save_post_metadata(sample_post.id, "T", "S", "alpha, beta")
            post = get_post_by_id(sample_post.id)
            assert set(t.slug for t in post.tags) == {"alpha", "beta"}

            # Second update: change to "gamma"
            save_post_metadata(sample_post.id, "T", "S", "gamma")
            post = get_post_by_id(sample_post.id)
            assert set(t.slug for t in post.tags) == {"gamma"}
