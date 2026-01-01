from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from content_indexer import index_all
from models import Category, Post, Tag
from security import slugify


def get_or_create_category(db: Session, slug: str, name: str) -> Category:
    slug = slugify(slug)
    name = (name or "").strip() or slug.replace("-", " ").title()

    c = db.query(Category).filter_by(slug=slug).one_or_none()
    if c:
        c.name = name
        return c

    c = Category(slug=slug, name=name)
    db.add(c)
    return c


def get_or_create_tag(db: Session, tag_slug: str) -> tuple[Tag, bool]:
    tag_slug = slugify(tag_slug)
    pretty = tag_slug.replace("-", " ").title()

    t = db.query(Tag).filter_by(slug=tag_slug).one_or_none()
    if t:
        return t, False

    t = Tag(slug=tag_slug, name=pretty)
    db.add(t)
    return t, True


def _unique_slug(db: Session, desired: str, *, post_id: int | None = None) -> str:
    base = slugify(desired) or "item"

    q = db.query(Post).filter(Post.slug == base)
    if post_id is not None:
        q = q.filter(Post.id != post_id)
    if q.count() == 0:
        return base

    i = 2
    while True:
        cand = f"{base}-{i}"
        q = db.query(Post).filter(Post.slug == cand)
        if post_id is not None:
            q = q.filter(Post.id != post_id)
        if q.count() == 0:
            return cand
        i += 1


@dataclass
class _Counters:
    created: int = 0
    updated: int = 0
    unpublished: int = 0


def sync_content(content_dir: str, db: Session) -> dict:
    indexed = index_all(content_dir)
    indexed_by_path = {p.source_path: p for p in indexed}

    existing_posts: List[Post] = db.query(Post).all()
    existing_by_path: Dict[str, Post] = {p.source_path: p for p in existing_posts}

    counters = _Counters()
    new_tags: List[str] = []

    # Cache categories and tags during sync to avoid duplicate queries
    category_cache: Dict[str, Category] = {}
    tag_cache: Dict[str, Tag] = {}

    try:
        with db.no_autoflush:
            for src_path, ip in indexed_by_path.items():
                # Use cached category if available
                cat_key = slugify(ip.category_slug)
                if cat_key in category_cache:
                    cat = category_cache[cat_key]
                else:
                    cat = get_or_create_category(db, ip.category_slug, ip.category_name)
                    category_cache[cat_key] = cat

                post = existing_by_path.get(src_path)

                # Fallback: if your DB stored relative paths earlier, src_path won’t match.
                # Since slug is UNIQUE, we can safely “adopt” the old row.
                if post is None:
                    post = db.query(Post).filter_by(slug=ip.slug).one_or_none()
                    if post is not None and post.source_path != src_path:
                        post.source_path = src_path
                        existing_by_path[src_path] = post

                if post is None:
                    resolved_slug = _unique_slug(db, ip.slug)
                    post = Post(
                        source_path=src_path,
                        slug=resolved_slug,
                        title=ip.title,
                        summary=ip.summary,
                        content_md=ip.content_md,
                        content_html=ip.content_html,
                        content_sha256=ip.content_sha256,
                        published=ip.published,
                        category=cat,
                        subpath=ip.subpath,
                    )
                    db.add(post)
                    existing_by_path[src_path] = post
                    counters.created += 1
                else:
                    # Update on content hash change
                    if post.content_sha256 != ip.content_sha256:
                        post.slug = _unique_slug(db, ip.slug, post_id=post.id)
                        post.title = ip.title
                        post.summary = ip.summary
                        post.content_md = ip.content_md
                        post.content_html = ip.content_html
                        post.content_sha256 = ip.content_sha256
                        post.subpath = ip.subpath
                        counters.updated += 1
                    else:
                        # keep these in sync anyway
                        post.title = ip.title
                        post.summary = ip.summary
                        post.subpath = ip.subpath

                    post.category = cat
                    post.published = ip.published

                # Tags: rewrite association each sync
                post.tags.clear()
                for tslug in ip.tags:
                    tslug = slugify(tslug)
                    if not tslug:
                        continue

                    # Use cached tag if available
                    if tslug in tag_cache:
                        tag = tag_cache[tslug]
                    else:
                        tag, was_created = get_or_create_tag(db, tslug)
                        tag_cache[tslug] = tag
                        if was_created:
                            new_tags.append(tag.name)
                    post.tags.append(tag)

        # Unpublish missing files (never delete)
        for src_path, post in list(existing_by_path.items()):
            if src_path not in indexed_by_path and post.published:
                post.published = False
                counters.unpublished += 1

        db.commit()

    except IntegrityError as e:
        db.rollback()
        raise RuntimeError(
            "Integrity error during content sync. "
            "Most likely a duplicate UNIQUE key (slug/source_path) or concurrent sync."
        ) from e
    except Exception:
        db.rollback()
        raise

    return {
        "created": counters.created,
        "updated": counters.updated,
        "unpublished": counters.unpublished,
        "deleted": 0,
        "total_indexed": len(indexed),
        "new_tags": sorted(set(new_tags)),
    }
