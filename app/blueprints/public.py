from __future__ import annotations

import re
from datetime import UTC, datetime
from flask import Blueprint, Response, abort, flash, redirect, render_template, request, send_from_directory, url_for
from extensions import limiter
from models import Category, MailingListSubscriber, Post, Tag, db
from security import slugify

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
@limiter.limit("60/minute")
def index():
    recent = (
        db.session.query(Post)
        .filter(Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .limit(50)
        .all()
    )
    categories = db.session.query(Category).order_by(Category.slug.asc()).all()
    return render_template("index.html", recent=recent, categories=categories)


@public_bp.route("/about")
def about():
    return render_template("about.html")



@public_bp.route("/contact")
def contact():
    return render_template("contact.html")


@public_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@public_bp.route("/terms")
def terms():
    return render_template("terms.html")


@public_bp.route("/p/<slug>/")
@limiter.limit("120/minute")
def post_view(slug: str):
    

    slug = slugify(slug)
    if not (1 <= len(slug) <= 100):
        abort(404)

    post = (
        db.session.query(Post)
        .filter(Post.slug == slug, Post.published.is_(True))
        .one_or_none()
    )
    if not post:
        abort(404)
    return render_template("post.html", post=post)


@public_bp.route("/c/<category>/")
@limiter.limit("120/minute")
def category_view(category: str):
    category = slugify(category)
    if not (1 <= len(category) <= 100):
        abort(404)

    cat = db.session.query(Category).filter_by(slug=category).one_or_none()
    if not cat:
        abort(404)

    posts = (
        db.session.query(Post)
        .filter(Post.category_id == cat.id, Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .all()
    )
    return render_template("category.html", category=cat, posts=posts)


@public_bp.route("/categories/")
@limiter.limit("60/minute")
def categories_index():
    categories = db.session.query(Category).order_by(Category.slug.asc()).all()
    return render_template("categories.html", categories=categories)


@public_bp.route("/projects/")
@limiter.limit("60/minute")
def projects_index():
    projects_cat = db.session.query(Category).filter_by(slug="projects").one_or_none()
    if not projects_cat:
        return render_template("projects.html", projects=[])

    projects = (
        db.session.query(Post)
        .filter(Post.category_id == projects_cat.id, Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .all()
    )
    return render_template("projects.html", projects=projects)


@public_bp.route("/tags/")
@limiter.limit("60/minute")
def tags_index():
    from services.tag_service import get_tags_with_counts
    tags_with_counts = get_tags_with_counts()
    return render_template("tags.html", tags_with_counts=tags_with_counts)


@public_bp.route("/t/<tag>/")
@limiter.limit("120/minute")
def tag_view(tag: str):
    tag = slugify(tag)
    if not (1 <= len(tag) <= 100):
        abort(404)

    t = db.session.query(Tag).filter_by(slug=tag).one_or_none()
    if not t:
        abort(404)

    posts = (
        db.session.query(Post)
        .join(Post.tags)
        .filter(Tag.id == t.id, Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .all()
    )
    return render_template("tag.html", tag=t, posts=posts)


@public_bp.route("/all/")
@limiter.limit("30/minute")
def all_posts():
    posts = (
        db.session.query(Post)
        .filter(Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .all()
    )
    return render_template("all_posts.html", posts=posts)


@public_bp.route("/subscribe", methods=["POST"])
@limiter.limit("5/minute")
def subscribe():
    email = (request.form.get("email") or "").strip().lower()

    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Please enter a valid email address.", "error")
        return redirect(request.referrer or url_for("public.index"))

    existing = db.session.query(MailingListSubscriber).filter_by(email=email).one_or_none()
    if existing and not existing.unsubscribed:
        flash("You're already subscribed!", "info")
        return redirect(request.referrer or url_for("public.index"))

    if existing and existing.unsubscribed:
        existing.unsubscribed = False
        existing.confirmed = False
    else:
        subscriber = MailingListSubscriber(email=email)
        db.session.add(subscriber)

    db.session.commit()
    flash("Thanks for subscribing! You'll hear from us soon.", "success")
    return redirect(request.referrer or url_for("public.index"))


@public_bp.route("/sitemap.xml")
@limiter.limit("10/minute")
def sitemap_xml():
    """Generate sitemap.xml dynamically from published routes and posts."""
    base = request.url_root.rstrip("/")
    now = datetime.now(UTC).strftime("%Y-%m-%d")

    urls = []

    # Static public pages
    static_routes = [
        (url_for("public.index"), "1.0", "daily"),
        (url_for("public.about"), "0.6", "monthly"),
        (url_for("public.contact"), "0.5", "monthly"),
        (url_for("public.all_posts"), "0.8", "daily"),
        (url_for("public.categories_index"), "0.7", "weekly"),
        (url_for("public.projects_index"), "0.7", "weekly"),
        (url_for("public.tags_index"), "0.6", "weekly"),
    ]
    for path, priority, freq in static_routes:
        urls.append(f'  <url><loc>{base}{path}</loc><lastmod>{now}</lastmod>'
                     f'<changefreq>{freq}</changefreq><priority>{priority}</priority></url>')

    # Published posts
    posts = (
        db.session.query(Post)
        .filter(Post.published.is_(True))
        .order_by(Post.updated_at.desc())
        .all()
    )
    for post in posts:
        lastmod = (post.updated_at or post.created_at or datetime.now(UTC)).strftime("%Y-%m-%d")
        loc = f"{base}{url_for('public.post_view', slug=post.slug)}"
        urls.append(f'  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>'
                     f'<changefreq>weekly</changefreq><priority>0.8</priority></url>')

    # Categories
    categories = db.session.query(Category).all()
    for cat in categories:
        loc = f"{base}{url_for('public.category_view', category=cat.slug)}"
        urls.append(f'  <url><loc>{loc}</loc><changefreq>weekly</changefreq>'
                     f'<priority>0.5</priority></url>')

    # Tags
    tags = db.session.query(Tag).all()
    for tag in tags:
        loc = f"{base}{url_for('public.tag_view', tag=tag.slug)}"
        urls.append(f'  <url><loc>{loc}</loc><changefreq>weekly</changefreq>'
                     f'<priority>0.4</priority></url>')

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>")

    return Response(xml, mimetype="application/xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@public_bp.route("/robots.txt")
def robots():
    return send_from_directory("public", "robots.txt")


@public_bp.route("/security.txt")
def security_txt():
    return send_from_directory("public", "security.txt")
