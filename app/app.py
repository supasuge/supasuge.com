from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Optional

from flask import Flask, abort, render_template, request
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config, get_config
from content_indexer import pygments_css
from database import get_engine_options
from models import db

from blueprints.public import public_bp, limiter as public_limiter
from blueprints.api import api_bp
from blueprints.admin import admin_bp
from blueprints.health import health_bp


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}


def create_app(config: Config | None = None) -> Flask:
    if config is None:
        cfg = get_config()
    else:
        cfg = config

    app = Flask(__name__)

    sqlalchemy_engine_options = get_engine_options(cfg.DATABASE_TYPE)

    # Flask-Limiter expects *_URI, but your env uses *_URL.
    ratelimit_storage_uri = cfg.RATELIMIT_STORAGE_URL

    app.config.from_mapping(
        SECRET_KEY=cfg.SECRET_KEY,
        SQLALCHEMY_DATABASE_URI=cfg.SQLALCHEMY_DATABASE_URI,
        SQLALCHEMY_TRACK_MODIFICATIONS=cfg.SQLALCHEMY_TRACK_MODIFICATIONS,
        SQLALCHEMY_ENGINE_OPTIONS=sqlalchemy_engine_options,

        MAX_CONTENT_LENGTH=cfg.MAX_UPLOAD_SIZE,

        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=cfg.COOKIE_SECURE,
        SESSION_COOKIE_SAMESITE=cfg.COOKIE_SAMESITE,

        RATELIMIT_STORAGE_URI=ratelimit_storage_uri,
        RATELIMIT_DEFAULT=cfg.RATELIMIT_DEFAULT,
        RATELIMIT_HEADERS_ENABLED=True,
    )

    if cfg.BEHIND_PROXY:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=cfg.PROXY_FIX_X_FOR,
            x_proto=cfg.PROXY_FIX_X_PROTO,
            x_host=cfg.PROXY_FIX_X_HOST,
        )

    db.init_app(app)

    csrf = CSRFProtect(app)
    csrf.exempt(api_bp)

    app.config.update(
        CONTENT_DIR=cfg.CONTENT_DIR,

        ADMIN_SSH_PUBLIC_KEY_PATH=cfg.ADMIN_SSH_PUBLIC_KEY_PATH,
        ADMIN_SSH_PRINCIPAL=cfg.ADMIN_SSH_PRINCIPAL,
        ADMIN_SSH_NAMESPACE=cfg.ADMIN_SSH_NAMESPACE,
        ADMIN_SESSION_TIMEOUT=cfg.ADMIN_SESSION_TIMEOUT,
        ADMIN_SESSION_RENEWAL=cfg.ADMIN_SESSION_RENEWAL,
        ADMIN_CHALLENGE_EXPIRY=cfg.ADMIN_CHALLENGE_EXPIRY,

        ANALYTICS_ENABLED=cfg.ANALYTICS_ENABLED,
        ANALYTICS_RETENTION_DAYS=cfg.ANALYTICS_RETENTION_DAYS,
        ANALYTICS_RESPECT_DNT=cfg.ANALYTICS_RESPECT_DNT,
        ANALYTICS_SALT=cfg.ANALYTICS_SALT,
        ANALYTICS_SESSION_TIMEOUT=cfg.ANALYTICS_SESSION_TIMEOUT,
        GEOIP_DB_PATH=cfg.GEOIP_DB_PATH,

        MAX_UPLOAD_SIZE=cfg.MAX_UPLOAD_SIZE,
        ALLOWED_EXTENSIONS=cfg.ALLOWED_EXTENSIONS,

        CELERY_BROKER_URL=cfg.CELERY_BROKER_URL,
        CELERY_RESULT_BACKEND=cfg.CELERY_RESULT_BACKEND,
    )

    public_limiter.init_app(app)

    allowed = {h.strip().lower() for h in (cfg.ALLOWED_HOSTS or []) if h.strip()}

    @app.before_request
    def _enforce_allowed_hosts():
        if not allowed:
            return
        host = (request.host or "").split(":", 1)[0].lower()
        if host not in allowed:
            app.logger.warning("Blocked Host header: %s", host)
            abort(400)

    @app.after_request
    def set_security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "geolocation=()"

        if cfg.ENABLE_HSTS:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        resp.headers["Content-Security-Policy"] = cfg.CSP
        return resp

    @app.context_processor
    def inject_globals():
        return {
            "site_year": datetime.now(UTC).year,
            "site_name": cfg.SITE_NAME,
            "site_url": cfg.SITE_URL,
            "pygments_css": pygments_css(),
        }

    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    return app


if __name__ == "__main__":
    # Dev-only runner. In Docker/prod you should use gunicorn.
    app = create_app()
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        debug=_truthy(os.getenv("FLASK_DEBUG", "0")),
    )
