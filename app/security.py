"""Input sanitization utilities."""

from __future__ import annotations

import re

SLUG_RE = re.compile(r"[^a-z0-9\-]+")


def slugify(text: str) -> str:
    t = (text or "").strip().lower().replace(" ", "-")
    t = SLUG_RE.sub("", t)
    t = re.sub(r"-{2,}", "-", t).strip("-")
    return t or "item"
