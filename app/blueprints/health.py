"""Health check endpoint for container orchestration."""

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from models import db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "healthy", "database": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": f"unhealthy: {e}"}), 503


@health_bp.route("/ready")
def readiness_check():
    checks = {"database": False, "redis": None}

    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Redis is optional (you use it mainly for limiter storage)
    try:
        redis_uri = current_app.config.get("RATELIMIT_STORAGE_URI", "")
        if isinstance(redis_uri, str) and redis_uri.startswith("redis://"):
            import redis  # type: ignore

            r = redis.from_url(redis_uri)
            r.ping()
            checks["redis"] = True
    except Exception:
        checks["redis"] = False

    status_code = 200 if checks["database"] else 503
    return jsonify({"status": "ready" if checks["database"] else "not_ready", "checks": checks}), status_code
