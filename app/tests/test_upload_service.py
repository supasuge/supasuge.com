"""Tests for services/upload_service.py."""

import os
import pytest
from io import BytesIO
from werkzeug.datastructures import FileStorage

from services.upload_service import (
    validate_markdown_upload,
    save_uploaded_markdown,
    upload_markdown_to_db,
    delete_markdown_file,
)
from models import Post, db


class TestValidateMarkdownUpload:
    def test_valid_md_file(self, app):
        with app.app_context():
            fs = FileStorage(stream=BytesIO(b"# Hello"), filename="test.md")
            valid, error = validate_markdown_upload(fs)
            assert valid is True
            assert error is None

    def test_no_file(self, app):
        with app.app_context():
            valid, error = validate_markdown_upload(FileStorage())
            assert valid is False

    def test_invalid_extension(self, app):
        with app.app_context():
            fs = FileStorage(stream=BytesIO(b"data"), filename="test.txt")
            valid, error = validate_markdown_upload(fs)
            assert valid is False
            assert "Invalid file type" in error


class TestUploadMarkdownToDb:
    def test_creates_post_in_db(self, app):
        with app.app_context():
            content = b"---\ntitle: Test Post\ntags:\n  - python\n---\n# Hello World\nContent here."
            fs = FileStorage(stream=BytesIO(content), filename="test-post.md")
            success, msg, post_id = upload_markdown_to_db(fs, "general")
            assert success is True
            assert post_id is not None

            post = db.session.query(Post).filter_by(id=post_id).one()
            assert post.title == "Test Post"
            assert "Hello World" in post.content_html
            assert post.content_sha256

    def test_updates_existing_post_with_same_slug(self, app):
        with app.app_context():
            fs1 = FileStorage(stream=BytesIO(b"# First version"), filename="my-post.md")
            success1, _, pid1 = upload_markdown_to_db(
                fs1, "general", {"title": "My Post", "slug": "my-post"}
            )
            assert success1

            fs2 = FileStorage(stream=BytesIO(b"# Updated version"), filename="my-post.md")
            success2, _, pid2 = upload_markdown_to_db(
                fs2, "general", {"title": "My Post", "slug": "my-post"}
            )
            assert success2
            # Should update same post, not create a new one
            assert pid1 == pid2
            post = db.session.query(Post).filter_by(id=pid1).one()
            assert "Updated version" in post.content_html

    def test_resolves_tags(self, app):
        with app.app_context():
            content = b"---\ntitle: Tagged Post\ntags:\n  - crypto\n  - ctf\n---\nContent"
            fs = FileStorage(stream=BytesIO(content), filename="tagged.md")
            success, _, post_id = upload_markdown_to_db(fs, "ctf")
            assert success
            post = db.session.query(Post).filter_by(id=post_id).one()
            tag_slugs = sorted(t.slug for t in post.tags)
            assert "crypto" in tag_slugs
            assert "ctf" in tag_slugs

    def test_frontmatter_overrides(self, app):
        with app.app_context():
            content = b"---\ntitle: From File\n---\nBody"
            fs = FileStorage(stream=BytesIO(content), filename="override.md")
            success, _, post_id = upload_markdown_to_db(
                fs, "general", {"title": "From Form"}
            )
            assert success
            post = db.session.query(Post).filter_by(id=post_id).one()
            assert post.title == "From Form"

    def test_no_frontmatter(self, app):
        with app.app_context():
            fs = FileStorage(stream=BytesIO(b"# Just Content\nNo frontmatter here"), filename="bare.md")
            success, _, post_id = upload_markdown_to_db(fs, "general")
            assert success
            post = db.session.query(Post).filter_by(id=post_id).one()
            assert post.title == "Just Content"

    def test_imports_obsidian_image_from_full_vault(self, app, tmp_path):
        with app.app_context():
            vault_root = tmp_path / "vault"
            pasted_dir = vault_root / "attachments" / "nested"
            pasted_dir.mkdir(parents=True)
            image_name = "Pasted image 20240705121438.png"
            source_image = pasted_dir / image_name
            source_image.write_bytes(b"\x89PNG\r\n\x1a\nfakepng")

            asset_output = tmp_path / "site-assets"
            app.config["OBSIDIAN_VAULT_ROOT"] = str(vault_root)
            app.config["MARKDOWN_ASSET_OUTPUT_DIR"] = str(asset_output)
            app.config["MARKDOWN_ASSET_URL_PREFIX"] = "/static/img/vault"

            md = f"![[{image_name}]]\n\n# CRT\n\nSummary text.".encode("utf-8")
            fs = FileStorage(stream=BytesIO(md), filename="crt.md")

            success, _, post_id = upload_markdown_to_db(fs, "general")
            assert success

            post = db.session.query(Post).filter_by(id=post_id).one()
            assert "/static/img/vault/" in post.content_md
            copied_assets = list(asset_output.glob("*.png"))
            assert len(copied_assets) == 1


class TestSaveUploadedMarkdownLegacy:
    """Tests for the backward-compatible wrapper."""

    def test_returns_success_and_message(self, app):
        with app.app_context():
            fs = FileStorage(stream=BytesIO(b"# Test content"), filename="legacy-test.md")
            success, msg = save_uploaded_markdown(fs, "general")
            assert success is True
            assert "created" in msg.lower() or "updated" in msg.lower()


class TestDeleteMarkdownFile:
    def test_virtual_path_noop(self, app):
        with app.app_context():
            success, msg = delete_markdown_file("upload://general/test.md")
            assert success is True

    def test_deletes_real_file(self, app, tmp_path):
        with app.app_context():
            app.config["CONTENT_DIR"] = str(tmp_path)
            md = tmp_path / "test.md"
            md.write_text("# Content")

            success, msg = delete_markdown_file(str(md))
            assert success is True
            assert not md.exists()

    def test_nonexistent_file(self, app, tmp_path):
        with app.app_context():
            app.config["CONTENT_DIR"] = str(tmp_path)
            success, msg = delete_markdown_file(str(tmp_path / "nope.md"))
            # File already gone is fine
            assert success is True

    def test_path_traversal_blocked(self, app, tmp_path):
        with app.app_context():
            app.config["CONTENT_DIR"] = str(tmp_path)
            success, msg = delete_markdown_file("/etc/passwd")
            assert success is False
            assert "security" in msg.lower()

    def test_non_markdown_blocked(self, app, tmp_path):
        with app.app_context():
            app.config["CONTENT_DIR"] = str(tmp_path)
            txt = tmp_path / "test.txt"
            txt.write_text("not markdown")
            success, msg = delete_markdown_file(str(txt))
            assert success is False
