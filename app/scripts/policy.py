from __future__ import annotations

from pathlib import Path


def main() -> None:
    problems = []

    if not Path("content").exists():
        problems.append("Missing /content directory.")

    if not Path("public/robots.txt").exists():
        problems.append("Missing public/robots.txt")

    if not Path("public/security.txt").exists():
        problems.append("Missing public/security.txt")
    
    if not Path('public/sitemap.xml').exists():
        problems.append("Missing public/sitemapp.xml")

    if problems:
        print("Problems:")
        for p in problems:
            print(f" - {p}")
        raise SystemExit(1)

    print("Looks sane enough.")


if __name__ == "__main__":
    main()
