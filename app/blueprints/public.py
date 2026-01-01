from __future__ import annotations

from flask import Blueprint, abort, render_template, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import Category, Post, Tag, db
from security import slugify

public_bp = Blueprint("public", __name__)

# Single limiter instance; configured in create_app()
limiter = Limiter(key_func=get_remote_address)


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


@public_bp.route("/robots.txt")
def robots():
    return send_from_directory("public", "robots.txt")


@public_bp.route("/security.txt")
def security_txt():
    return send_from_directory("public", "security.txt")
