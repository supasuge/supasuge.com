"""Admin post management routes.

All content operations go directly to the database.
"""

from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, url_for, jsonify
from blueprints.admin import admin_bp
from auth.decorators import require_admin
from models import Category, db
from services.post_service import (
    delete_post,
    get_all_posts,
    get_post_by_id,
    save_post_content,
    save_post_metadata,
    toggle_post_published,
)


@admin_bp.route("/posts")
@require_admin
def posts_list():
    posts = get_all_posts(published_only=False)
    return render_template("admin/posts_list.html", posts=posts)


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@require_admin
def post_new():
    if request.method == "GET":
        categories = db.session.query(Category).order_by(Category.name).all()
        return render_template("admin/post_new.html", categories=categories)

    if "markdown" not in request.files:
        flash("No file uploaded", "error")
        return redirect(url_for("admin.post_new"))

    from services.upload_service import upload_markdown_to_db

    file = request.files["markdown"]

    if not file.filename:
        flash("No file selected", "error")
        return redirect(url_for("admin.post_new"))

    current_app.logger.info(
        "Upload attempt: filename=%s, content_type=%s, content_length=%s",
        file.filename, file.content_type, request.content_length,
    )

    max_size = current_app.config.get("MAX_UPLOAD_SIZE", 2 * 1024 * 1024)
    if request.content_length and request.content_length > max_size:
        flash(f"File too large (max {max_size // 1024 // 1024}MB)", "error")
        return redirect(url_for("admin.post_new"))

    category_slug = request.form.get("category", "general")
    published = request.form.get("published", "true") == "true"

    frontmatter = {}
    if request.form.get("title"):
        frontmatter["title"] = request.form.get("title")
    if request.form.get("summary"):
        frontmatter["summary"] = request.form.get("summary")
    if request.form.get("tags"):
        tags = [t.strip() for t in request.form.get("tags").split(",") if t.strip()]
        if tags:
            frontmatter["tags"] = tags
    frontmatter["published"] = published

    success, result, post_id = upload_markdown_to_db(file, category_slug, frontmatter)

    if not success:
        flash(f"Upload failed: {result}", "error")
        return redirect(url_for("admin.post_new"))

    flash(result, "success")
    return redirect(url_for("admin.posts_list"))


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@require_admin
def post_edit(post_id: int):
    post = get_post_by_id(post_id)
    if not post:
        flash("Post not found", "error")
        return redirect(url_for("admin.posts_list"))

    if request.method == "GET":
        categories = db.session.query(Category).order_by(Category.name).all()
        return render_template("admin/post_edit.html", post=post, categories=categories)

    try:
        title = request.form.get("title", post.title)
        summary = request.form.get("summary", post.summary)
        tags_csv = request.form.get("tag_slugs", "")
        published = request.form.get("published", "false") == "true"

        save_post_metadata(post_id, title, summary, tags_csv)

        post = get_post_by_id(post_id)
        post.published = published
        db.session.commit()

        content_md = request.form.get("content_md")
        if content_md is not None:
            save_post_content(post_id, content_md)

        flash("Post updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update post: {e}")
        flash(f"Update failed: {str(e)}", "error")

    return redirect(url_for("admin.post_edit", post_id=post_id))


@admin_bp.route("/posts/<int:post_id>/save-content", methods=["POST"])
@require_admin
def post_save_content(post_id: int):
    """AJAX endpoint to save post content without full page reload."""
    data = request.get_json(silent=True)
    if not data or "content_md" not in data:
        return jsonify({"success": False, "error": "No content provided"}), 400

    try:
        post = save_post_content(post_id, data["content_md"])
        if not post:
            return jsonify({"success": False, "error": "Post not found"}), 404
        return jsonify({"success": True, "message": "Content saved"})
    except Exception as e:
        current_app.logger.error(f"Failed to save content: {e}")
        return jsonify({"success": False, "error": "Failed to save content"}), 500


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@require_admin
def post_delete(post_id: int):
    post = get_post_by_id(post_id)
    if not post:
        flash("Post not found", "error")
        return redirect(url_for("admin.posts_list"))

    if delete_post(post_id):
        flash("Post deleted successfully!", "success")
    else:
        flash("Failed to delete post from database", "error")

    return redirect(url_for("admin.posts_list"))


@admin_bp.route("/posts/<int:post_id>/toggle", methods=["POST"])
@require_admin
def post_toggle_published(post_id: int):
    post = toggle_post_published(post_id)
    if not post:
        return jsonify({"success": False, "error": "Post not found"}), 404

    flash(f"Post '{post.title}' {'published' if post.published else 'unpublished'}", "success")
    return redirect(url_for("admin.posts_list"))
