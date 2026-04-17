"""Tests for content_sync.py - filesystem to database synchronization."""

import pytest
from pathlib import Path

from content_sync import (
    get_or_create_category,
    get_or_create_tag,
    sync_content,
)
from models import Category, Post, Tag, db


class TestGetOrCreateCategory:
    def test_creates_new_category(self, app):
        with app.app_context():
            cat = get_or_create_category(db.session, "linux", "Linux")
            db.session.flush()
            assert cat.slug == "linux"
            assert cat.name == "Linux"

    def test_returns_existing(self, app):
        with app.app_context():
            cat1 = get_or_create_category(db.session, "linux", "Linux")
            db.session.flush()
            cat2 = get_or_create_category(db.session, "linux", "Linux Updated")
            assert cat1.id == cat2.id
            assert cat2.name == "Linux Updated"

    def test_auto_names_from_slug(self, app):
        with app.app_context():
            cat = get_or_create_category(db.session, "my-category", "")
            assert cat.name == "My Category"


class TestGetOrCreateTag:
    def test_creates_new_tag(self, app):
        with app.app_context():
            tag, created = get_or_create_tag(db.session, "python")
            db.session.flush()
            assert tag.slug == "python"
            assert created is True

    def test_returns_existing(self, app):
        with app.app_context():
            tag1, c1 = get_or_create_tag(db.session, "python")
            db.session.flush()
            tag2, c2 = get_or_create_tag(db.session, "python")
            assert tag1.id == tag2.id
            assert c2 is False


class TestSyncContent:
    def test_sync_creates_posts(self, app, tmp_path):
        cat_dir = tmp_path / "ctf"
        cat_dir.mkdir()
        (cat_dir / "my-writeup.md").write_text(
            "---\ntitle: My Writeup\nsummary: A CTF writeup\ntags: [crypto]\npublished: true\n---\n\nContent here\n",
            encoding="utf-8",
        )

        with app.app_context():
            results = sync_content(str(tmp_path), db.session)
            assert results["created"] == 1
            assert results["total_indexed"] == 1

            post = db.session.query(Post).filter_by(slug="my-writeup").one_or_none()
            assert post is not None
            assert post.title == "My Writeup"
            assert post.published is True

    def test_sync_updates_on_change(self, app, tmp_path):
        cat_dir = tmp_path / "general"
        cat_dir.mkdir()
        md = cat_dir / "post.md"
        md.write_text(
            "---\ntitle: Post\npublished: true\n---\n\nVersion 1\n",
            encoding="utf-8",
        )

        with app.app_context():
            sync_content(str(tmp_path), db.session)
            post = db.session.query(Post).filter_by(slug="post").one()
            assert "Version 1" in post.content_md

        md.write_text(
            "---\ntitle: Post Updated\npublished: true\n---\n\nVersion 2\n",
            encoding="utf-8",
        )

        with app.app_context():
            results = sync_content(str(tmp_path), db.session)
            assert results["updated"] == 1
            post = db.session.query(Post).filter_by(slug="post").one_or_none()
            if post:
                assert post.title == "Post Updated"

    def test_sync_unpublishes_missing(self, app, tmp_path):
        cat_dir = tmp_path / "general"
        cat_dir.mkdir()
        md = cat_dir / "temp.md"
        md.write_text(
            "---\ntitle: Temporary\npublished: true\n---\n\nTemporary content\n",
            encoding="utf-8",
        )

        with app.app_context():
            sync_content(str(tmp_path), db.session)
            post = db.session.query(Post).filter_by(slug="temporary").one()
            assert post.published is True

        md.unlink(missing_ok=True)

        with app.app_context():
            results = sync_content(str(tmp_path), db.session)
            assert results["unpublished"] == 1
            post = db.session.query(Post).filter_by(slug="temporary").one()
            assert post.published is False

    def test_empty_directory(self, app, tmp_path):
        with app.app_context():
            results = sync_content(str(tmp_path), db.session)
            assert results["created"] == 0
            assert results["total_indexed"] == 0

    def test_tags_created(self, app, tmp_path):
        cat_dir = tmp_path / "general"
        cat_dir.mkdir()
        (cat_dir / "tagged.md").write_text(
            "---\ntitle: Tagged\ntags: [alpha, beta]\npublished: true\n---\n\nContent\n",
            encoding="utf-8",
        )

        with app.app_context():
            results = sync_content(str(tmp_path), db.session)
            assert len(results["new_tags"]) >= 2

            post = db.session.query(Post).filter_by(slug="tagged").one()
            tag_slugs = [t.slug for t in post.tags]
            assert "alpha" in tag_slugs
            assert "beta" in tag_slugs
