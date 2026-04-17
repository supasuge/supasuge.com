from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, url_for

from auth.decorators import require_admin
from blueprints.admin import admin_bp
from models import Post, db
from services.analytics_service import get_analytics_summary, get_post_analytics


@admin_bp.route("/analytics")
@require_admin
def analytics_overview():
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
        summary = get_analytics_summary(days=days)
    except Exception as e:
        current_app.logger.error(f"Error fetching analytics summary: {e}")
        flash("Error loading analytics data. Please check the database.", "error")
        summary = {
            "total_views": 0,
            "unique_visitors": 0,
            "top_posts": [],
            "top_referrers": [],
            "top_countries": [],
            "daily_views": [],
        }
        days = 30

    return render_template(
        "admin/analytics/overview.html",
        summary=summary,
        days=days,
    )


@admin_bp.route("/analytics/posts")
@require_admin
def analytics_posts():
    try:
        posts = db.session.query(Post).order_by(Post.title.asc()).all()
    except Exception as e:
        current_app.logger.error(f"Error fetching posts: {e}")
        flash("Error loading posts. Please check the database.", "error")
        posts = []

    return render_template(
        "admin/analytics/posts.html",
        posts=posts
    )


@admin_bp.route("/analytics/posts/<int:post_id>")
@require_admin
def analytics_post_detail(post_id: int):
    """Detailed analytics for a single post."""
    try:
        post = db.session.query(Post).filter_by(id=post_id).one_or_none()
        if not post:
            flash("Post not found", "error")
            return redirect(url_for("admin.analytics_posts"))

        stats = get_post_analytics(post_id=post.id)
    except Exception as e:
        current_app.logger.error(f"Error fetching post analytics for post {post_id}: {e}")
        flash("Error loading post analytics. Please check the database.", "error")
        return redirect(url_for("admin.analytics_posts"))

    return render_template(
        "admin/analytics/post_detail.html",
        post=post,
        stats=stats,
    )
