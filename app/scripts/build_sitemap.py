"""Generate sitemap.xml from published posts in the database."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from models import Post, db


def main() -> None:
    app = create_app()

    with app.app_context():
        site_url = app.config["SITE_URL"].rstrip("/")
        today = date.today().isoformat()

        posts = (
            db.session.query(Post)
            .filter(Post.published.is_(True))
            .all()
        )

        urls: set[str] = {f"{site_url}/"}
        for p in posts:
            urls.add(f"{site_url}/p/{escape(p.slug)}/")
            if p.category:
                urls.add(f"{site_url}/c/{escape(p.category.slug)}/")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u in sorted(urls):
        xml.append("  <url>")
        xml.append(f"    <loc>{u}</loc>")
        xml.append(f"    <lastmod>{today}</lastmod>")
        xml.append("  </url>")
    xml.append("</urlset>")

    out = REPO_ROOT / "public" / "sitemap.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(xml) + "\n", encoding="utf-8")
    print(f"Wrote {len(urls)} URLs to {out}")


if __name__ == "__main__":
    main()
