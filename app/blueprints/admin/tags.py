"""Admin tag management routes."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for, jsonify
from blueprints.admin import admin_bp
from auth.decorators import require_admin
from models import Tag, db
from security import slugify
from services.tag_service import get_tags_with_counts, get_unused_tags


@admin_bp.route("/tags")
@require_admin
def tags_list():
    """
    Tag management page.

    Shows:
    - Table of tags with name, slug, post count
    - Inline edit for renaming
    - Delete with confirmation
    - Separate section for unused tags
    """
    tags_with_counts = get_tags_with_counts()
    unused_tags = get_unused_tags()

    return render_template(
        "admin/tags_list.html",
        tags_with_counts=tags_with_counts,
        unused_tags=unused_tags,
    )


@admin_bp.route("/tags/new", methods=["POST"])
@require_admin
def tag_create():
    """Create a new tag."""
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Tag name cannot be empty", "error")
        return redirect(url_for("admin.tags_list"))

    slug = slugify(name)

    existing = db.session.query(Tag).filter_by(slug=slug).one_or_none()
    if existing:
        flash("Tag already exists", "error")
        return redirect(url_for("admin.tags_list"))

    tag = Tag(name=name, slug=slug)
    db.session.add(tag)
    db.session.commit()

    flash(f"Tag '{name}' created", "success")
    return redirect(url_for("admin.tags_list"))


@admin_bp.route("/tags/<int:tag_id>/edit", methods=["POST"])
@require_admin
def tag_edit(tag_id: int):
    """Rename a tag."""
    tag = db.session.query(Tag).filter_by(id=tag_id).one_or_none()
    if not tag:
        flash("Tag not found", "error")
        return redirect(url_for("admin.tags_list"))

    new_name = (request.form.get("name") or "").strip()
    if not new_name:
        flash("Tag name cannot be empty", "error")
        return redirect(url_for("admin.tags_list"))

    new_slug = slugify(new_name)

    # Check for slug conflicts
    conflict = (
        db.session.query(Tag)
        .filter(Tag.slug == new_slug, Tag.id != tag.id)
        .one_or_none()
    )
    if conflict:
        flash("Another tag with that name already exists", "error")
        return redirect(url_for("admin.tags_list"))

    tag.name = new_name
    tag.slug = new_slug
    db.session.commit()

    flash("Tag updated", "success")
    return redirect(url_for("admin.tags_list"))


@admin_bp.route("/tags/<int:tag_id>/delete", methods=["POST"])
@require_admin
def tag_delete(tag_id: int):
    """Delete a tag (removes from all posts)."""
    tag = db.session.query(Tag).filter_by(id=tag_id).one_or_none()
    if not tag:
        flash("Tag not found", "error")
        return redirect(url_for("admin.tags_list"))

    post_count = len(tag.posts)
    tag_name = tag.name

    db.session.delete(tag)
    db.session.commit()

    if post_count > 0:
        flash(
            f"Tag '{tag_name}' deleted (removed from {post_count} post{'s' if post_count != 1 else ''})",
            "success",
        )
    else:
        flash(f"Tag '{tag_name}' deleted", "success")

    return redirect(url_for("admin.tags_list"))


@admin_bp.route("/tags/search")
@require_admin
def tag_search_json():
    """JSON endpoint for tag autocomplete."""
    query = request.args.get("q", "").lower().strip()

    # SECURITY: Use parameterized LIKE with bind parameter to prevent SQL injection
    # Pattern is constructed safely using SQLAlchemy's % operator
    search_pattern = f"%{query}%"

    tags = (
        db.session.query(Tag.slug)
        .filter(Tag.slug.like(search_pattern))
        .order_by(Tag.slug.asc())
        .limit(10)
        .all()
    )

    return jsonify([t.slug for t in tags])
