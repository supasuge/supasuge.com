from __future__ import annotations

from pathlib import Path
from flask import Blueprint, abort, send_from_directory, current_app

media_bp = Blueprint("media", __name__, url_prefix="/media")

@media_bp.route("/img/<path:filename>")
def media_image(filename: str):
    """
    Serve images referenced by markdown content.

    This is intentionally separate from Flask's default /static
    so content assets are explicitly controlled.
    """
    static_dir = Path(current_app.root_path) / "static" / "img"

    # Resolve and enforce containment
    try:
        target = (static_dir / filename).resolve()
        if static_dir.resolve() not in target.parents and target != static_dir.resolve():
            abort(404)
    except Exception:
        abort(404)

    if not target.exists() or not target.is_file():
        abort(404)

    return send_from_directory(static_dir, filename)
