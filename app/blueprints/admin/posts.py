"""Admin post management routes."""

from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, url_for
from blueprints.admin import admin_bp
from auth.decorators import require_admin
from models import Category, db
from services.post_service import (
    delete_post,
    get_all_posts,
    get_post_by_id,
    sync_posts_from_filesystem,
    toggle_post_published,
)
from services.upload_service import delete_markdown_file, save_uploaded_markdown


def format_sync_message(results: dict, prefix: str = "Content synced!") -> str:
    """
    Format a sync results message with optional new tags warning.

    Args:
        results: Sync results dictionary
        prefix: Message prefix

    Returns:
        Formatted message string
    """
    msg = (
        f"{prefix} Created: {results['created']}, "
        f"Updated: {results['updated']}"
    )

    # Include deleted count if syncing (not on upload)
    if "deleted" in results:
        msg += f", Deleted: {results['deleted']}, Total: {results['total_indexed']}"

    # Show warning if new tags were created
    if results.get("new_tags"):
        msg += f" | New tags created: {', '.join(results['new_tags'])}"

    return msg


@admin_bp.route("/posts")
@require_admin
def posts_list():
    """
    List all posts with management actions.

    Shows: title, category, published status, created date
    Actions: edit, delete, toggle published
    """
    posts = get_all_posts(published_only=False)
    return render_template("admin/posts_list.html", posts=posts)


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@require_admin
def post_new():
    """
    Upload a new markdown post.

    GET: Show upload form with category selection
    POST: Validate and save uploaded file, trigger sync
    """
    if request.method == "GET":
        categories = db.session.query(Category).order_by(Category.name).all()
        return render_template("admin/post_new.html", categories=categories)

    # POST: Handle upload
    if "markdown" not in request.files:
        flash("No file uploaded", "error")
        return redirect(url_for("admin.post_new"))

    file = request.files["markdown"]
    category_slug = request.form.get("category", "general")
    published = request.form.get("published", "true") == "true"

    # Optional frontmatter override
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

    # Save file
    success, result = save_uploaded_markdown(file, category_slug, frontmatter)

    if not success:
        flash(f"Upload failed: {result}", "error")
        return redirect(url_for("admin.post_new"))

    # Trigger content sync to add to database
    try:
        sync_results = sync_posts_from_filesystem()
        flash(format_sync_message(sync_results, "Post uploaded successfully!"), "success")
    except Exception as e:
        current_app.logger.error(f"Sync failed after upload: {e}")
        flash(f"File saved but sync failed: {str(e)}", "warning")

    return redirect(url_for("admin.posts_list"))


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@require_admin
def post_edit(post_id: int):
    """
    Edit an existing post's metadata.

    Note: This updates database fields only.
    To edit markdown content, edit the source file directly.

    GET: Show edit form with current values
    POST: Update post metadata
    """
    post = get_post_by_id(post_id)
    if not post:
        flash("Post not found", "error")
        return redirect(url_for("admin.posts_list"))

    if request.method == "GET":
        categories = db.session.query(Category).order_by(Category.name).all()
        return render_template("admin/post_edit.html", post=post, categories=categories)

    # POST: Update metadata
    # Note: For full content editing, user should edit the source markdown file
    # and trigger re-sync, or we'd need a markdown editor UI

    post.published = request.form.get("published", "false") == "true"

    # Handle tag updates
    if "tag_slugs" in request.form:
        from services.tag_service import attach_tags_to_post

        tag_slugs_raw = request.form.get("tag_slugs", "")
        tag_slugs = [s.strip() for s in tag_slugs_raw.split(",") if s.strip()]
        attach_tags_to_post(post_id, tag_slugs)

    try:
        db.session.commit()
        flash("Post updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update post: {e}")
        flash(f"Update failed: {str(e)}", "error")

    return redirect(url_for("admin.posts_list"))


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@require_admin
def post_delete(post_id: int):
    """
    Delete a post (both database record and source file).

    POST only (CSRF protection)
    """
    post = get_post_by_id(post_id)
    if not post:
        flash("Post not found", "error")
        return redirect(url_for("admin.posts_list"))

    # Delete source file if it exists
    if post.source_path:
        delete_success, delete_msg = delete_markdown_file(post.source_path)
        if not delete_success:
            flash(f"Warning: Failed to delete source file: {delete_msg}", "warning")

    # Delete from database
    if delete_post(post_id):
        flash("Post deleted successfully!", "success")
    else:
        flash("Failed to delete post from database", "error")

    return redirect(url_for("admin.posts_list"))


@admin_bp.route("/posts/<int:post_id>/toggle", methods=["POST"])
@require_admin
def post_toggle_published(post_id: int):
    """
    Toggle post published status (AJAX endpoint).

    POST only
    Returns: JSON response for AJAX calls
    """
    from flask import jsonify

    post = toggle_post_published(post_id)

    if not post:
        return jsonify({"success": False, "error": "Post not found"}), 404

    return jsonify({"success": True, "published": post.published}), 200


@admin_bp.route("/posts/sync", methods=["POST"])
@require_admin
def posts_sync():
    """
    Manually trigger content sync from filesystem.

    POST only
    Useful after editing markdown files directly
    """
    try:
        results = sync_posts_from_filesystem()
        flash(format_sync_message(results), "success")
    except Exception as e:
        current_app.logger.error(f"Sync failed: {e}")
        flash(f"Sync failed: {str(e)}", "error")

    return redirect(url_for("admin.posts_list"))
