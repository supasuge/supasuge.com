"""API blueprint for analytics tracking and data endpoints."""

from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Import routes to register them with the blueprint
from blueprints.api import tracking  # noqa: E402, F401

__all__ = ["api_bp"]
