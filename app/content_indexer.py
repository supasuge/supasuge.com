from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
import bleach
import frontmatter
import markdown as md
from pygments.formatters import HtmlFormatter

from security import slugify

MD_EXTENSIONS = [
    "fenced_code",
    "codehilite",
    "tables",
    "toc",
    "admonition",
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
    }
)

ALLOWED_ATTRS = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "loading"],
    "span": ["class"],
    "code": ["class"],
    "pre": ["class"],
    "div": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}
# SECURITY: Removed "data" protocol to prevent XSS via data URIs
# Data URIs like data:text/html,<script>alert('XSS')</script> are dangerous
ALLOWED_PROTOCOLS = bleach.sanitizer.ALLOWED_PROTOCOLS


def pygments_css() -> str:
    return HtmlFormatter().get_style_defs(".codehilite")


def markdown_to_safe_html(markdown_text: str) -> str:
    html = md.markdown(
        markdown_text,
        extensions=MD_EXTENSIONS,
        extension_configs={
            "codehilite": {
                "guess_lang": False,
                "noclasses": False,
                "pygments_style": "monokai",
            },
            "toc": {"permalink": True},
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
    return cleaned


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_date(v: object) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


@dataclass(frozen=True)
class IndexedPost:
    source_path: str
    slug: str
    title: str
    summary: str
    tags: List[str]
    published: bool
    date: Optional[datetime]
    category_slug: str
    category_name: str
    subpath: str
    content_md: str
    content_html: str
    content_sha256: str


def derive_category(content_root: Path, md_path: Path) -> Tuple[str, str, str]:
    """
    Category = first directory under /content.
    /content/ctf/x.md => ("ctf", "Ctf", "x.md")
    /content/hello.md => ("general", "General", "hello.md")
    /content/articles/cheatsheets/a.md => ("articles", "Articles", "cheatsheets/a.md")
    """
    rel = md_path.relative_to(content_root)
    parts = rel.parts
    if len(parts) == 1:
        return ("general", "General", parts[0])

    category = parts[0]
    subpath = str(Path(*parts[1:]))
    return (slugify(category), category.strip().title(), subpath)


def iter_markdown_files(content_dir: str) -> Iterable[Path]:
    root = Path(content_dir).resolve()
    if not root.exists():
        return []

    for p in root.rglob("*.md"):
        # Skip symlinks (content should be content, not a filesystem wormhole)
        try:
            if p.is_symlink():
                continue
            rp = p.resolve()
        except Exception:
            continue

        # Enforce containment to prevent traversal tricks
        if root not in rp.parents and rp != root:
            continue

        yield rp


def index_file(content_root: Path, md_path: Path) -> IndexedPost:
    post = frontmatter.load(str(md_path))
    meta = post.metadata or {}

    title = str(meta.get("title") or md_path.stem)
    slug = slugify(str(meta.get("slug") or title))
    summary = str(meta.get("summary") or "")

    tags_raw = meta.get("tags") or []
    tags = [slugify(str(t)) for t in tags_raw if str(t).strip()]
    # We store the tag slug, but keep name separately in DB (we’ll use original casing later if you care).

    published = bool(meta.get("published", True))
    date = parse_date(meta.get("date"))

    category_slug, category_name, subpath = derive_category(content_root, md_path)

    content_md = post.content or ""
    content_html = markdown_to_safe_html(content_md)
    content_hash = sha256_text(content_md + "|" + str(meta))

    return IndexedPost(
        source_path=str(md_path),
        slug=slug,
        title=title,
        summary=summary,
        tags=tags,
        published=published,
        date=date,
        category_slug=category_slug,
        category_name=category_name,
        subpath=subpath,
        content_md=content_md,
        content_html=content_html,
        content_sha256=content_hash,
    )


def index_all(content_dir: str) -> List[IndexedPost]:
    root = Path(content_dir).resolve()
    posts: List[IndexedPost] = []
    for f in iter_markdown_files(content_dir):
        posts.append(index_file(root, f))
    return posts
