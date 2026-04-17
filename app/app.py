from __future__ import annotations
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
import secrets
from flask import Flask, abort, g, render_template, request, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config, get_config
from content_indexer import pygments_css
from database import get_database_uri, get_engine_options
from models import db
from startup import bootstrap_app, maybe_sync_content
from blueprints.public import public_bp
from extensions import limiter as public_limiter
from blueprints.api import api_bp
from blueprints.admin import admin_bp
from blueprints.health import health_bp
from blueprints.media import media_bp
import re

IMG_PLACEHOLDER_RE = re.compile(r'__IMG__:(?P<path>[^"\'>]+)')

def resolve_image_urls(html: str) -> str:
    def repl(m):
        path = m.group("path")
        return url_for("static", filename=f"img/{path}")

    return IMG_PLACEHOLDER_RE.sub(repl, html)


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}

def create_app(config: Config | None = None) -> Flask:
    cfg = config or get_config()

    # 🔑 CRITICAL: Explicit instance_path so Flask + SQLite agree on reality
    app_root = Path(__file__).resolve().parent
    instance_path = app_root / "instance"

    app = Flask(
        __name__,
        instance_path=str(instance_path),
        instance_relative_config=True,
    )
    # Ensure instance directory exists
    instance_path.mkdir(parents=True, exist_ok=True)
    
    db_uri, db_type = get_database_uri(instance_path)

    sqlalchemy_engine_options = get_engine_options(db_type)

    # Flask-Limiter expects *_URI
    ratelimit_storage_uri = cfg.RATELIMIT_STORAGE_URL

    #  Core Flask config 
    app.config.from_mapping(
        SECRET_KEY=cfg.SECRET_KEY,

        SQLALCHEMY_DATABASE_URI=db_uri,
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

    # Handle reverse proxy... Caddy in this case
    if cfg.BEHIND_PROXY:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=cfg.PROXY_FIX_X_FOR,
            x_proto=cfg.PROXY_FIX_X_PROTO,
            x_host=cfg.PROXY_FIX_X_HOST,
        )

    #  Logging 
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, log_level, logging.INFO),
    )

    #  App-specific config (before extensions that need it) 
    app.config.update(
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
        OBSIDIAN_VAULT_ROOT=cfg.OBSIDIAN_VAULT_ROOT,
        MARKDOWN_ASSET_URL_PREFIX=cfg.MARKDOWN_ASSET_URL_PREFIX,
        CONTENT_DIR=cfg.CONTENT_DIR,
        AUTO_SYNC_CONTENT=cfg.AUTO_SYNC_CONTENT,
        CONTENT_SYNC_INTERVAL_SECONDS=cfg.CONTENT_SYNC_INTERVAL_SECONDS,
    )

    #  Extensions 
    db.init_app(app)
    bootstrap_app(app)

    csrf = CSRFProtect(app)
    # Exempt only specific API endpoints (not the entire blueprint)
    from blueprints.api.tracking import track_pageview, track_heartbeat
    csrf.exempt(track_pageview)
    csrf.exempt(track_heartbeat)

    public_limiter.init_app(app)

    #  Host allowlist enforcement 
    allowed_hosts = {h.strip().lower() for h in (cfg.ALLOWED_HOSTS or []) if h.strip()}

    @app.before_request
    def _enforce_allowed_hosts():
        if not allowed_hosts:
            return
        host = (request.host or "").split(":", 1)[0].lower()
        if host not in allowed_hosts:
            app.logger.warning("Blocked Host header: %s", host)
            abort(400)

    @app.before_request
    def _maybe_sync_content():
        maybe_sync_content(app)

    #  CSP nonce generation 
    @app.before_request
    def generate_csp_nonce():
        """Generate a unique nonce for each request for CSP."""
        g.csp_nonce = secrets.token_urlsafe(32)

    #  Security headers 
    @app.after_request
    def set_security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "geolocation=()"

        if cfg.ENABLE_HSTS:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Build CSP with nonce for inline scripts
        # Note: 'unsafe-inline' for styles is needed for Pygments code
        # highlighting. This is acceptable as CSS-based attacks are
        # significantly less severe than script injection.
        nonce = getattr(g, 'csp_nonce', '')
        csp = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        resp.headers["Content-Security-Policy"] = csp
        return resp

    #  Template globals 
    @app.context_processor
    def inject_globals():
        return {
            "site_year": datetime.now(UTC).year,
            "site_name": cfg.SITE_NAME,
            "site_url": cfg.SITE_URL,
            "pygments_css": pygments_css(),
            "csp_nonce": getattr(g, 'csp_nonce', ''),
            "analytics_enabled": cfg.ANALYTICS_ENABLED,
            "analytics_respect_dnt": cfg.ANALYTICS_RESPECT_DNT,
            "analytics_retention_days": cfg.ANALYTICS_RETENTION_DAYS,
        }

    #  Blueprints 
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(media_bp)
    app.jinja_env.filters["resolve_images"] = resolve_image_urls

    #  Error handlers 
    @app.errorhandler(400)
    def bad_request(e):
        return render_template(
            "error.html", 
            code=400, 
            title="Bad Request",
            message="The server could not understand your request."
            ), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, title="Forbidden",
                               message="You don't have permission to access this resource."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template("error.html", code=413, title="File Too Large",
                               message="The uploaded file exceeds the maximum allowed size."), 413

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template("error.html", code=429, title="Too Many Requests",
                               message="You've made too many requests. Please wait a moment and try again."), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html"), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        debug=_truthy(os.getenv("FLASK_DEBUG", "0")),
    )
