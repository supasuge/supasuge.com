"""Analytics tracking API endpoints."""

from __future__ import annotations

from flask import current_app, jsonify, request
from blueprints.api import api_bp
from services.analytics_service import record_pageview
from models import PageView, db


@api_bp.route("/track/pageview", methods=["POST"])
def track_pageview():
    """
    Record a pageview from the JavaScript tracker.
    """
    if not current_app.config.get("ANALYTICS_ENABLED", True):
        return jsonify({"success": False, "error": "Analytics disabled"}), 403

    if current_app.config.get("ANALYTICS_RESPECT_DNT", True):
        dnt = request.headers.get("DNT") or request.headers.get("dnt")
        if dnt == "1":
            return jsonify({"success": True, "message": "DNT respected"}), 200

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No JSON data"}), 400

    path = data.get("path")
    session_id = data.get("session_id")
    visitor_id = data.get("visitor_id") or request.cookies.get("analytics_vid")

    if not path or not session_id or not visitor_id:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    if not isinstance(visitor_id, str) or len(visitor_id) < 32:
        return jsonify({"success": False, "error": "Invalid visitor_id"}), 400

    ip_address = request.remote_addr or "0.0.0.0"
    user_agent = data.get("user_agent") or request.headers.get("User-Agent", "")
    referrer = data.get("referrer")
    screen_dims = data.get("screen") if isinstance(data.get("screen"), dict) else None
    post_id = data.get("post_id")

    try:
        pageview = record_pageview(
            path=path,
            visitor_hash=visitor_id,     # stored as visitor_hash in DB
            session_hash=session_id,     # stored as session_hash in DB
            referrer=referrer,
            user_agent=user_agent,
            ip_address=ip_address,
            screen_dims=screen_dims,
            post_id=post_id if isinstance(post_id, int) else None,
        )

        return jsonify({"success": True, "pageview_id": pageview.id}), 201

    except Exception as e:
        current_app.logger.error(f"Error recording pageview: {e}")
        return jsonify({"success": False, "error": "Internal error"}), 500


@api_bp.route("/track/heartbeat", methods=["POST"])
def track_heartbeat():
    """
    Update time on page for an existing pageview.
    """
    if not current_app.config.get("ANALYTICS_ENABLED", True):
        return jsonify({"success": False, "error": "Analytics disabled"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No JSON data"}), 400

    pageview_id = data.get("pageview_id")
    time_spent = data.get("time_spent")

    if not pageview_id or time_spent is None:
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    try:
        pageview = db.session.query(PageView).filter_by(id=pageview_id).one_or_none()
        if not pageview:
            return jsonify({"success": False, "error": "Pageview not found"}), 404

        current = int(pageview.time_on_page or 0)
        incoming = int(time_spent)

        if incoming < 0:
            incoming = 0

        pageview.time_on_page = max(current, incoming)
        db.session.commit()

        return jsonify({"success": True}), 200

    except Exception as e:
        current_app.logger.error(f"Error updating heartbeat: {e}")
        return jsonify({"success": False, "error": "Internal error"}), 500
