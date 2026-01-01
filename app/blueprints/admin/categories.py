from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from blueprints.admin import admin_bp
from auth.decorators import require_admin
from models import Category, Post, db
from security import slugify


@admin_bp.route("/categories")
@require_admin
def categories_list():
    categories = db.session.query(Category).order_by(Category.slug.asc()).all()
    return render_template("admin/categories_list.html", categories=categories)


@admin_bp.route("/categories/new", methods=["POST"])
@require_admin
def category_create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Category name cannot be empty", "error")
        return redirect(url_for("admin.categories_list"))

    slug = slugify(name)

    existing = db.session.query(Category).filter_by(slug=slug).one_or_none()
    if existing:
        flash("Category already exists", "error")
        return redirect(url_for("admin.categories_list"))

    cat = Category(name=name, slug=slug)
    db.session.add(cat)
    db.session.commit()

    flash(f"Category '{name}' created", "success")
    return redirect(url_for("admin.categories_list"))


@admin_bp.route("/categories/<int:category_id>/edit", methods=["POST"])
@require_admin
def category_edit(category_id: int):
    cat = db.session.query(Category).filter_by(id=category_id).one_or_none()
    if not cat:
        flash("Category not found", "error")
        return redirect(url_for("admin.categories_list"))

    new_name = (request.form.get("name") or "").strip()
    if not new_name:
        flash("Category name cannot be empty", "error")
        return redirect(url_for("admin.categories_list"))

    new_slug = slugify(new_name)

    conflict = (
        db.session.query(Category)
        .filter(Category.slug == new_slug, Category.id != cat.id)
        .one_or_none()
    )
    if conflict:
        flash("Another category with that name already exists", "error")
        return redirect(url_for("admin.categories_list"))

    cat.name = new_name
    cat.slug = new_slug
    db.session.commit()

    flash("Category updated", "success")
    return redirect(url_for("admin.categories_list"))


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@require_admin
def category_delete(category_id: int):
    cat = db.session.query(Category).filter_by(id=category_id).one_or_none()
    if not cat:
        flash("Category not found", "error")
        return redirect(url_for("admin.categories_list"))

    # Ensure fallback category exists
    fallback = db.session.query(Category).filter_by(slug="general").one_or_none()
    if not fallback:
        fallback = Category(name="General", slug="general")
        db.session.add(fallback)
        db.session.flush()

    # Reassign posts
    (
        db.session.query(Post)
        .filter(Post.category_id == cat.id)
        .update({Post.category_id: fallback.id})
    )

    db.session.delete(cat)
    db.session.commit()

    flash(f"Category '{cat.name}' deleted (posts moved to General)", "success")
    return redirect(url_for("admin.categories_list"))
