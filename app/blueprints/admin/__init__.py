from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

from blueprints.admin import auth
from blueprints.admin import posts
from blueprints.admin import analytics
from blueprints.admin import categories  # ← NEW
from blueprints.admin import tags

__all__ = ["admin_bp"]
