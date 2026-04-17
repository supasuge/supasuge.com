"""Tests for content_archive module."""

import json
import os
import tarfile

import pytest


class TestArchiveSyncedFiles:
    """Test archiving markdown files after sync."""

    def test_archive_single_file(self, app, tmp_path):
        """Archive a single .md file into tar.gz with manifest."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\nContent here", encoding="utf-8")

        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        with app.app_context():
            from content_archive import archive_synced_files

            counts = archive_synced_files(
                [str(md_file)],
                archive_path=archive_path,
                manifest_path=manifest_path,
                delete_after=True,
            )

        assert counts["archived"] == 1
        assert counts["deleted"] == 1
        assert counts["errors"] == 0
        assert not md_file.exists(), "Source file should be deleted"
        assert os.path.exists(archive_path)

        # Verify manifest
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert len(manifest) == 1
        assert manifest[0]["source_path"] == str(md_file)
        assert len(manifest[0]["sha256"]) == 64

    def test_archive_multiple_files(self, app, tmp_path):
        """Archive multiple files in one call."""
        files = []
        for i in range(3):
            f = tmp_path / f"post_{i}.md"
            f.write_text(f"# Post {i}\nContent", encoding="utf-8")
            files.append(str(f))

        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        with app.app_context():
            from content_archive import archive_synced_files

            counts = archive_synced_files(
                files,
                archive_path=archive_path,
                manifest_path=manifest_path,
                delete_after=True,
            )

        assert counts["archived"] == 3
        assert counts["deleted"] == 3

        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert len(manifest) == 3

    def test_archive_skip_missing_files(self, app, tmp_path):
        """Skip files that don't exist on disk."""
        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        with app.app_context():
            from content_archive import archive_synced_files

            counts = archive_synced_files(
                ["/nonexistent/file.md"],
                archive_path=archive_path,
                manifest_path=manifest_path,
            )

        assert counts["skipped"] == 1
        assert counts["archived"] == 0

    def test_archive_no_delete_when_disabled(self, app, tmp_path):
        """Don't delete files when delete_after=False."""
        md_file = tmp_path / "keep.md"
        md_file.write_text("# Keep me", encoding="utf-8")

        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        with app.app_context():
            from content_archive import archive_synced_files

            counts = archive_synced_files(
                [str(md_file)],
                archive_path=archive_path,
                manifest_path=manifest_path,
                delete_after=False,
            )

        assert counts["archived"] == 1
        assert counts["deleted"] == 0
        assert md_file.exists(), "File should still exist"

    def test_archive_appends_to_existing(self, app, tmp_path):
        """Appending to an existing archive adds new entries."""
        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        # First batch
        f1 = tmp_path / "first.md"
        f1.write_text("# First", encoding="utf-8")

        with app.app_context():
            from content_archive import archive_synced_files

            archive_synced_files(
                [str(f1)],
                archive_path=archive_path,
                manifest_path=manifest_path,
            )

        # Second batch
        f2 = tmp_path / "second.md"
        f2.write_text("# Second", encoding="utf-8")

        with app.app_context():
            counts = archive_synced_files(
                [str(f2)],
                archive_path=archive_path,
                manifest_path=manifest_path,
            )

        assert counts["archived"] == 1

        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert len(manifest) == 2

    def test_already_archived_file_skipped_or_deleted(self, app, tmp_path):
        """Files already in manifest are skipped (or deleted if delete_after)."""
        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        md_file = tmp_path / "already.md"
        md_file.write_text("# Already archived", encoding="utf-8")

        with app.app_context():
            from content_archive import archive_synced_files

            # Archive once
            archive_synced_files(
                [str(md_file)],
                archive_path=archive_path,
                manifest_path=manifest_path,
                delete_after=False,
            )

            # Try again - should skip since already in manifest
            counts = archive_synced_files(
                [str(md_file)],
                archive_path=archive_path,
                manifest_path=manifest_path,
                delete_after=True,
            )

        assert counts["archived"] == 0
        assert counts["deleted"] == 1  # deletes the already-archived file


class TestVerifyArchiveIntegrity:
    """Test archive integrity verification."""

    def test_verify_good_archive(self, app, tmp_path):
        """Verification succeeds for a correctly archived file."""
        md_file = tmp_path / "good.md"
        md_file.write_text("# Good content", encoding="utf-8")

        archive_path = str(tmp_path / "archive.tar.gz")
        manifest_path = str(tmp_path / "manifest.json")

        with app.app_context():
            from content_archive import archive_synced_files, verify_archive_integrity

            archive_synced_files(
                [str(md_file)],
                archive_path=archive_path,
                manifest_path=manifest_path,
                delete_after=False,
            )

            results = verify_archive_integrity(
                archive_path=archive_path,
                manifest_path=manifest_path,
            )

        assert len(results) == 1
        assert results[0]["status"] == "ok"

    def test_verify_missing_archive(self, app, tmp_path):
        """Verification reports error for missing archive file."""
        with app.app_context():
            from content_archive import verify_archive_integrity

            results = verify_archive_integrity(
                archive_path=str(tmp_path / "nonexistent.tar.gz"),
                manifest_path=str(tmp_path / "manifest.json"),
            )

        assert len(results) == 1
        assert "error" in results[0]
