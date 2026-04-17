"""Decorators for admin authentication and authorization."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import current_app, g, redirect, request, url_for

from .ssh_auth import verify_admin_session


def require_admin(f: Callable) -> Callable:
    """Protect admin routes with SSH-key-authenticated session cookie."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.cookies.get("admin_session")

        if not session_token:
            current_app.logger.debug("No admin session cookie found")
            return redirect(url_for("admin.login"))

        session = verify_admin_session(session_token)
        if not session:
            current_app.logger.warning("Invalid admin session")
            return redirect(url_for("admin.login"))

        g.admin_session = session
        g.admin_key_fingerprint = session.key_fingerprint

        current_app.logger.debug(f"Admin authenticated: {session.key_fingerprint}")
        return f(*args, **kwargs)

    return decorated_function
