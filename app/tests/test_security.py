"""Tests for security.py - slugify utility."""

from security import slugify


class TestSlugify:
    def test_basic_text(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters_removed(self):
        assert slugify("Hello! @World#") == "hello-world"

    def test_multiple_dashes_collapsed(self):
        assert slugify("hello---world") == "hello-world"

    def test_leading_trailing_dashes_stripped(self):
        assert slugify("-hello-world-") == "hello-world"

    def test_empty_returns_item(self):
        assert slugify("") == "item"

    def test_none_returns_item(self):
        assert slugify(None) == "item"

    def test_preserves_numbers(self):
        assert slugify("post-123") == "post-123"

    def test_unicode_stripped(self):
        result = slugify("caf\u00e9 latt\u00e9")
        assert result == "caf-latt"

    def test_whitespace_to_dashes(self):
        assert slugify("multiple   spaces") == "multiple-spaces"
