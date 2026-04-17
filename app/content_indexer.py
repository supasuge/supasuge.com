"""Markdown-to-HTML pipeline and content parsing utilities.

All content lives in the database. This module provides:
- Markdown rendering (with Pygments, Obsidian syntax, math support)
- Frontmatter parsing from raw markdown strings
- HTML sanitization via bleach
- Content hashing for change detection
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

import bleach
import frontmatter
import markdown as md
from pygments.formatters import HtmlFormatter

from security import slugify

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Markdown extensions & sanitization config
# ---------------------------------------------------------------------------

MD_EXTENSIONS = [
    "fenced_code",
    "codehilite",
    "tables",
    "toc",
    "admonition",
    "nl2br",
    "sane_lists",
    "smarty",
]

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {
        "p", "pre", "code", "span",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "br",
        "ul", "ol", "li",
        "blockquote",
        "table", "thead", "tbody", "tr", "th", "td",
        "img",
        "div",
        "del", "ins", "sup", "sub",
        "details", "summary",
        "kbd", "mark"
    }
)

ALLOWED_ATTRS = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel", "class"],   # class needed for .headerlink CSS
    "img": ["src", "alt", "title", "loading", "width", "height"],
    "span": ["class"],
    "code": ["class"],
    "pre": ["class"],
    "div": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
    "details": ["open"],
    # id needed for TOC anchor targets
    "h1": ["id"], "h2": ["id"], "h3": ["id"], "h4": ["id"], "h5": ["id"], "h6": ["id"],
}
ALLOWED_PROTOCOLS = bleach.sanitizer.ALLOWED_PROTOCOLS

# ---------------------------------------------------------------------------
# Pygments CSS helper
# ---------------------------------------------------------------------------


def pygments_css() -> str:
    """Return the Pygments stylesheet for `.codehilite` blocks."""
    return HtmlFormatter(style="monokai").get_style_defs(".codehilite")


# ---------------------------------------------------------------------------
# Image rewriting
# ---------------------------------------------------------------------------

IMG_SRC_RE = re.compile(
    r'(<img[^>]+src=["\'])([^"\']+)(["\'])',
    re.IGNORECASE,
)

OBSIDIAN_IMG_RE = re.compile(
    r'!\[\[([^\]|]+\.(png|jpg|jpeg|gif|svg|webp))(?:\|[^\]]+)?\]\]', re.IGNORECASE
)
OBSIDIAN_HIGHLIGHT_RE = re.compile(r'==(.*?)==')
OBSIDIAN_CALLOUT_RE = re.compile(
    r'^>\s*\[!(\w+)\]\s*(.*?)$',
    re.MULTILINE,
)


def preprocess_obsidian_syntax(text: str) -> str:
    """Convert Obsidian-specific markdown syntax to standard markdown."""
    text = OBSIDIAN_HIGHLIGHT_RE.sub(r'<mark>\1</mark>', text)
    text = OBSIDIAN_IMG_RE.sub(r'![\1](\1)', text)

    def callout_repl(m):
        callout_type = m.group(1).lower()
        title = m.group(2).strip()
        if title:
            return f'!!! {callout_type} "{title}"'
        return f'!!! {callout_type}'

    text = OBSIDIAN_CALLOUT_RE.sub(callout_repl, text)
    return text


def extract_title_from_markdown(markdown_text: str) -> Optional[str]:
    """Extract the first H1-style heading from markdown if present."""
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("# "):
            continue
        title = stripped[2:].strip()
        if title:
            return title
    return None


def extract_summary_from_markdown(markdown_text: str, *, limit: int = 220) -> str:
    """Extract a short summary from the first paragraph-like block."""
    paragraphs: list[str] = []
    current: list[str] = []

    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        if stripped.startswith(("#", "![", "![[", "> [!", "```", "---")):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        current.append(stripped)

    if current:
        paragraphs.append(" ".join(current))

    for paragraph in paragraphs:
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", paragraph).strip()
        cleaned = re.sub(r"!\[\[[^\]]+\]\]", "", cleaned).strip()
        if not cleaned:
            continue
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"

    return ""


def rewrite_image_src(html: str) -> str:
    """Rewrite local image src to placeholder tokens for later URL resolution."""

    def repl(m):
        prefix, src, suffix = m.groups()
        if src.startswith(("http://", "https://")):
            return m.group(0)
        src = src.lstrip("./")
        if src.startswith("static/img/"):
            src = src[len("static/img/"):]
        elif src.startswith("/static/img/"):
            src = src[len("/static/img/"):]
        return f'{prefix}__IMG__:{src}{suffix}'

    return IMG_SRC_RE.sub(repl, html)


# ---------------------------------------------------------------------------
# Math protection (preserve LaTeX through markdown+bleach)
# ---------------------------------------------------------------------------

DISPLAY_MATH_RE = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
INLINE_MATH_RE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')


def _protect_math(text: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}
    display_index = 0
    inline_index = 0

    def _replace_display(m: re.Match) -> str:
        nonlocal display_index
        key = f"MATHBLOCK_{display_index}_END"
        display_index += 1
        placeholders[key] = f"$${m.group(1)}$$"
        return key

    def _replace_inline(m: re.Match) -> str:
        nonlocal inline_index
        key = f"MATHINLINE_{inline_index}_END"
        inline_index += 1
        placeholders[key] = f"${m.group(1)}$"
        return key

    text = DISPLAY_MATH_RE.sub(_replace_display, text)
    text = INLINE_MATH_RE.sub(_replace_inline, text)
    return text, placeholders


def _restore_math(html: str, placeholders: dict[str, str]) -> str:
    # Replace longest keys first to prevent MATHINLINE_1 from matching
    # inside MATHINLINE_10, MATHINLINE_11, etc.
    for key in sorted(placeholders, key=len, reverse=True):
        html = html.replace(key, placeholders[key])
    return html


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------


def markdown_to_safe_html(markdown_text: str) -> str:
    """Convert markdown to sanitized HTML with Pygments, math, and Obsidian support."""
    markdown_text = preprocess_obsidian_syntax(markdown_text)
    markdown_text, math_placeholders = _protect_math(markdown_text)

    html = md.markdown(
        markdown_text,
        extensions=MD_EXTENSIONS,
        extension_configs={
            "codehilite": {
                "guess_lang": True,
                "noclasses": False,
                "pygments_style": "monokai",
            },
            "toc": {"permalink": False},
        },
        output_format="html5",
    )

    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    cleaned = bleach.linkify(cleaned, callbacks=[bleach.callbacks.nofollow])
    cleaned = rewrite_image_src(cleaned)
    cleaned = _restore_math(cleaned, math_placeholders)
    return cleaned


# ---------------------------------------------------------------------------
# Hashing / date helpers
# ---------------------------------------------------------------------------


def sha256_text(s: str) -> str:
    """SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_date(v: object) -> Optional[datetime]:
    """Parse a date value from frontmatter (string, date, or datetime)."""
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------


def validate_frontmatter(meta: dict, source: str = "<input>") -> List[str]:
    """Validate frontmatter fields. Returns list of warning strings."""
    warnings = []

    if "title" in meta and not isinstance(meta["title"], str):
        warnings.append(f"{source}: 'title' should be a string, got {type(meta['title']).__name__}")

    if "summary" in meta and not isinstance(meta["summary"], str):
        warnings.append(f"{source}: 'summary' should be a string, got {type(meta['summary']).__name__}")

    if "tags" in meta:
        tags = meta["tags"]
        if not isinstance(tags, list):
            warnings.append(f"{source}: 'tags' should be a list, got {type(tags).__name__}")
        elif not all(isinstance(t, str) for t in tags):
            warnings.append(f"{source}: all tags should be strings")

    if "published" in meta and not isinstance(meta["published"], bool):
        warnings.append(f"{source}: 'published' should be true/false, got {type(meta['published']).__name__}")

    if "date" in meta:
        d = meta["date"]
        if not isinstance(d, (str, datetime, date)):
            warnings.append(f"{source}: 'date' should be a date string or datetime, got {type(d).__name__}")
        elif isinstance(d, str) and parse_date(d) is None:
            warnings.append(f"{source}: 'date' value '{d}' is not a valid ISO 8601 date")

    if "slug" in meta:
        slug = meta["slug"]
        if not isinstance(slug, str):
            warnings.append(f"{source}: 'slug' should be a string")
        elif not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', str(slug).lower()) and len(str(slug)) > 1:
            warnings.append(f"{source}: 'slug' value '{slug}' contains invalid characters")

    known_keys = {"title", "summary", "tags", "published", "date", "slug", "draft", "aliases", "cssclass"}
    unknown = set(meta.keys()) - known_keys
    if unknown:
        warnings.append(f"{source}: unknown frontmatter keys: {', '.join(sorted(unknown))}")

    return warnings


# ---------------------------------------------------------------------------
# Parsed post dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedPost:
    """Result of parsing a markdown string (frontmatter + body)."""
    slug: str
    title: str
    summary: str
    tags: List[str]
    published: bool
    date: Optional[datetime]
    category_slug: str
    category_name: str
    content_md: str
    content_html: str
    content_sha256: str


# ---------------------------------------------------------------------------
# Parse markdown from string (the main entry point for DB-only workflow)
# ---------------------------------------------------------------------------


def parse_markdown_string(
    raw_markdown: str,
    *,
    default_category: str = "general",
    default_title: str = "Untitled",
) -> ParsedPost:
    """Parse a raw markdown string (with optional YAML frontmatter) into a ParsedPost.

    This is the primary entry point for the DB-only content workflow.
    No filesystem access is needed.

    Args:
        raw_markdown: Full markdown text, optionally with YAML frontmatter.
        default_category: Category slug if none specified in frontmatter.
        default_title: Title if none specified in frontmatter.

    Returns:
        ParsedPost with all fields populated.
    """
    parsed = frontmatter.loads(raw_markdown)
    meta = parsed.metadata or {}

    warnings = validate_frontmatter(meta, "<input>")
    for w in warnings:
        logger.warning(w)

    title = str(meta.get("title") or default_title)
    content_md = parsed.content or ""
    derived_title = extract_title_from_markdown(content_md)
    if not meta.get("title") and derived_title:
        title = derived_title

    slug = slugify(str(meta.get("slug") or title))
    summary = str(meta.get("summary") or "")
    if not summary:
        summary = extract_summary_from_markdown(content_md)

    tags_raw = meta.get("tags") or []
    if isinstance(tags_raw, str):
        tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
    tags = [slugify(str(t)) for t in tags_raw if str(t).strip()]

    if "draft" in meta and "published" not in meta:
        published = not bool(meta["draft"])
    else:
        published = bool(meta.get("published", True))

    date_val = parse_date(meta.get("date"))

    category_slug = slugify(str(meta.get("category") or default_category))
    category_name = category_slug.replace("-", " ").title()

    content_html = markdown_to_safe_html(content_md)
    content_hash = sha256_text(content_md)

    return ParsedPost(
        slug=slug,
        title=title,
        summary=summary,
        tags=tags,
        published=published,
        date=date_val,
        category_slug=category_slug,
        category_name=category_name,
        content_md=content_md,
        content_html=content_html,
        content_sha256=content_hash,
    )


def render_post_as_markdown(
    title: str,
    summary: str,
    tags: List[str],
    published: bool,
    content_md: str,
    slug: str = "",
) -> str:
    """Reconstruct a full markdown document (frontmatter + body) from post fields.

    Useful for exporting posts from the database.
    """
    import yaml

    meta = {"title": title, "summary": summary, "published": published}
    if tags:
        meta["tags"] = tags
    if slug:
        meta["slug"] = slug

    fm_block = "---\n" + yaml.dump(meta, default_flow_style=False, allow_unicode=True) + "---\n\n"
    return fm_block + content_md
