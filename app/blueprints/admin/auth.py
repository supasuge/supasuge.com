"""Admin authentication routes using SSH key challenge/response."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import (
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from sqlalchemy import func

from blueprints.admin import admin_bp
from extensions import limiter
from auth import (
    create_admin_session,
    generate_challenge,
    revoke_session,
    verify_signature,
)
from auth.decorators import require_admin
from models import AuthChallenge, PageView, db


def _cleanup_expired_challenges() -> None:
    """Remove expired challenges from the database (participates in caller's transaction)."""
    db.session.query(AuthChallenge).filter(
        AuthChallenge.expires_at < datetime.now(UTC)
    ).delete()


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5/minute")  # Strict rate limit for admin login
def login():
    if request.method == "GET":
        challenge = generate_challenge()

        expiry_seconds = int(current_app.config.get("ADMIN_CHALLENGE_EXPIRY", 300))
        expires_at = datetime.now(UTC) + timedelta(seconds=expiry_seconds)

        _cleanup_expired_challenges()

        db.session.add(AuthChallenge(challenge=challenge, expires_at=expires_at))
        db.session.commit()

        return render_template(
            "admin/login.html",
            challenge=challenge,
            ssh_namespace=current_app.config.get("ADMIN_SSH_NAMESPACE", "supasuge-admin"),
        )

    challenge = request.form.get("challenge")
    signed_message = request.form.get("signed_message")

    if not challenge or not signed_message:
        flash("Missing challenge or signature", "error")
        return redirect(url_for("admin.login"))

    _cleanup_expired_challenges()

    # Look up challenge in DB (must exist, not expired, not already used)
    ch = db.session.query(AuthChallenge).filter_by(
        challenge=challenge, used=False
    ).filter(AuthChallenge.expires_at > datetime.now(UTC)).one_or_none()

    if not ch:
        flash("Challenge expired or invalid", "error")
        return redirect(url_for("admin.login"))

    # Mark as used (single-use)
    ch.used = True
    db.session.commit()

    ok, fingerprint = verify_signature(
        challenge=challenge,
        signed_message=signed_message,
    )

    if not ok or not fingerprint:
        flash("Invalid SSH signature", "error")
        return redirect(url_for("admin.login"))

    token = create_admin_session(fingerprint, request)

    response = make_response(redirect(url_for("admin.dashboard")))
    response.set_cookie(
        "admin_session",
        token,
        httponly=True,
        secure=current_app.config.get("COOKIE_SECURE", True),
        samesite="Strict",
        max_age=int(current_app.config.get("ADMIN_SESSION_TIMEOUT", 28800)),
    )

    flash("Authenticated successfully", "success")
    return response


@admin_bp.route("/logout", methods=["POST"])
def logout():
    token = request.cookies.get("admin_session")
    if token:
        revoke_session(token)

    response = make_response(redirect(url_for("public.index")))
    response.set_cookie("admin_session", "", expires=0, httponly=True, secure=True, samesite="Strict")
    flash("Logged out", "info")
    return response


@admin_bp.route("/dashboard")
@require_admin
def dashboard():
    """
    Minimal admin dashboard.

    Displays top paths by pageviews (all-time). This avoids depending on
    half-implemented analytics dashboard modules.
    """
    top = []
    try:
        top = (
            db.session.query(PageView.path, func.count(PageView.id).label("views"))
            .group_by(PageView.path)
            .order_by(func.count(PageView.id).desc())
            .limit(20)
            .all()
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching analytics data: {e}")
        flash("Error loading analytics data. Database may not be initialized.", "error")

    return render_template("admin/dashboard.html", top=top)
