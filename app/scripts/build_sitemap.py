from __future__ import annotations

import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# Ensure we run from repo root and imports work regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from app import create_app  # app.py module in repo root
from config import Config
from models import db, Post


def main() -> None:
    app = create_app()
    cfg = Config()

    with app.app_context():
        posts = (
            db.session.query(Post)
            .filter(Post.published.is_(True))
            .all()
        )

        urls = [f"{cfg.SITE_URL}/"]
        for p in posts:
            urls.append(f"{cfg.SITE_URL}/p/{p.slug}/")
            urls.append(f"{cfg.SITE_URL}/c/{p.category.slug}/")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in sorted(set(urls)):
        xml.append("  <url>")
        xml.append(f"    <loc>{escape(u)}</loc>")
        xml.append("  </url>")
    xml.append("</urlset>")

    out = REPO_ROOT / "public" / "sitemap.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(xml) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
