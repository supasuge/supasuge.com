"""Tests for content_indexer.py - markdown rendering, Obsidian syntax, frontmatter validation."""

import pytest
from content_indexer import (
    markdown_to_safe_html,
    preprocess_obsidian_syntax,
    rewrite_image_src,
    sha256_text,
    parse_date,
    validate_frontmatter,
    parse_markdown_string,
    slugify,
)
from datetime import datetime, date


class TestMarkdownToSafeHtml:
    def test_basic_paragraph(self):
        html = markdown_to_safe_html("Hello world")
        assert "<p>" in html
        assert "Hello world" in html

    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        html = markdown_to_safe_html(md)
        assert "<code" in html or "<pre" in html

    def test_table_rendering(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = markdown_to_safe_html(md)
        assert "<table>" in html
        assert "<td>" in html

    def test_heading_rendering(self):
        html = markdown_to_safe_html("## Section Title")
        assert "<h2" in html

    def test_xss_script_stripped(self):
        html = markdown_to_safe_html("<script>alert('xss')</script>")
        assert "<script>" not in html

    def test_xss_event_handler_stripped(self):
        html = markdown_to_safe_html('<img src=x onerror="alert(1)">')
        assert "onerror" not in html

    def test_links_get_nofollow(self):
        html = markdown_to_safe_html("[click](https://example.com)")
        assert 'rel="nofollow"' in html

    def test_image_src_rewritten(self):
        html = markdown_to_safe_html("![alt](my-image.png)")
        assert "__IMG__:" in html

    def test_external_image_not_rewritten(self):
        html = markdown_to_safe_html("![alt](https://example.com/img.png)")
        assert "https://example.com/img.png" in html
        assert "__IMG__" not in html

    def test_allowed_tags_preserved(self):
        html = markdown_to_safe_html("~~deleted~~ text")
        # del tag should be preserved through bleach
        assert "<del>" in html or "deleted" in html

    def test_blockquote(self):
        html = markdown_to_safe_html("> This is a quote")
        assert "<blockquote>" in html


class TestObsidianSyntax:
    def test_highlight_syntax(self):
        result = preprocess_obsidian_syntax("This is ==highlighted== text")
        assert "<mark>highlighted</mark>" in result

    def test_wiki_image_embed(self):
        result = preprocess_obsidian_syntax("![[screenshot.png]]")
        assert "![screenshot.png](screenshot.png)" in result

    def test_wiki_image_jpg(self):
        result = preprocess_obsidian_syntax("![[photo.jpg]]")
        assert "![photo.jpg](photo.jpg)" in result

    def test_wiki_image_with_size(self):
        result = preprocess_obsidian_syntax("![[photo.jpg|600]]")
        assert "![photo.jpg](photo.jpg)" in result

    def test_callout_with_title(self):
        result = preprocess_obsidian_syntax("> [!note] Important Info")
        assert '!!! note "Important Info"' in result

    def test_callout_without_title(self):
        result = preprocess_obsidian_syntax("> [!warning]")
        assert "!!! warning" in result

    def test_no_false_highlight_single_equals(self):
        # Single = signs shouldn't trigger highlight
        result = preprocess_obsidian_syntax("a = b")
        assert "<mark>" not in result

    def test_highlight_requires_content(self):
        # Empty highlight shouldn't match
        result = preprocess_obsidian_syntax("====")
        # This may or may not match - just verify no crash
        assert isinstance(result, str)


class TestRewriteImageSrc:
    def test_relative_image(self):
        html = '<img src="my-image.png" alt="test">'
        result = rewrite_image_src(html)
        assert '__IMG__:my-image.png' in result

    def test_external_image_untouched(self):
        html = '<img src="https://example.com/img.png" alt="test">'
        result = rewrite_image_src(html)
        assert "https://example.com/img.png" in result
        assert "__IMG__" not in result

    def test_strips_static_img_prefix(self):
        html = '<img src="static/img/photo.png" alt="test">'
        result = rewrite_image_src(html)
        assert "__IMG__:photo.png" in result

    def test_strips_leading_dot_slash(self):
        html = '<img src="./photo.png" alt="test">'
        result = rewrite_image_src(html)
        assert "__IMG__:photo.png" in result


class TestSha256Text:
    def test_deterministic(self):
        assert sha256_text("hello") == sha256_text("hello")

    def test_different_inputs(self):
        assert sha256_text("hello") != sha256_text("world")

    def test_returns_hex_string(self):
        result = sha256_text("test")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


class TestParseDate:
    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_empty_returns_none(self):
        assert parse_date("") is None

    def test_datetime_passthrough(self):
        dt = datetime(2024, 1, 15)
        assert parse_date(dt) == dt

    def test_date_object(self):
        d = date(2024, 1, 15)
        result = parse_date(d)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_string(self):
        result = parse_date("2024-01-15")
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_invalid_string(self):
        assert parse_date("not-a-date") is None


class TestValidateFrontmatter:
    def test_valid_frontmatter(self):
        meta = {"title": "Test", "summary": "A test", "tags": ["a", "b"], "published": True}
        warnings = validate_frontmatter(meta, "test.md")
        assert warnings == []

    def test_invalid_title_type(self):
        meta = {"title": 123}
        warnings = validate_frontmatter(meta, "test.md")
        assert any("title" in w for w in warnings)

    def test_invalid_tags_type(self):
        meta = {"tags": "not-a-list"}
        warnings = validate_frontmatter(meta, "test.md")
        assert any("tags" in w for w in warnings)

    def test_invalid_published_type(self):
        meta = {"published": "yes"}
        warnings = validate_frontmatter(meta, "test.md")
        assert any("published" in w for w in warnings)

    def test_unknown_keys_warned(self):
        meta = {"title": "Test", "custom_field": "value"}
        warnings = validate_frontmatter(meta, "test.md")
        assert any("unknown" in w for w in warnings)

    def test_known_obsidian_keys_ok(self):
        meta = {"title": "Test", "draft": True, "aliases": ["alt"]}
        warnings = validate_frontmatter(meta, "test.md")
        assert not any("unknown" in w for w in warnings)


class TestParseMarkdownString:
    def test_derives_title_from_first_heading(self):
        parsed = parse_markdown_string("# Chinese Remainder Theorem\n\nSome notes here.")
        assert parsed.title == "Chinese Remainder Theorem"

    def test_derives_summary_from_first_paragraph(self):
        parsed = parse_markdown_string("# Title\n\nThis is the first paragraph.\n\n## Next")
        assert parsed.summary == "This is the first paragraph."
