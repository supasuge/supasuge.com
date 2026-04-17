#!/usr/bin/env python3
"""Create a new post directly in the database.

Usage:
    uv run python scripts/new_post.py <category> <title> [options]
    uv run python scripts/new_post.py -i  # interactive mode

All content is stored in the database — no files are written to disk.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import textwrap
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from security import slugify


def _ensure_min_env() -> None:
    if not os.getenv("SECRET_KEY"):
        os.environ["SECRET_KEY"] = f"dev-{secrets.token_hex(24)}"
    if not os.getenv("ANALYTICS_SALT"):
        os.environ["ANALYTICS_SALT"] = secrets.token_hex(24)


def get_existing_categories() -> list[str]:
    """Get categories from the database."""
    from models import Category, db
    return [c.slug for c in db.session.query(Category).order_by(Category.slug).all()]


def prompt_choice(prompt: str, choices: list[str], allow_new: bool = False) -> str:
    print(f"\n{prompt}\n" + "-" * 50)
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")
    if allow_new:
        print(f"  {len(choices) + 1}. [Create new]")
    print("-" * 50)

    while True:
        try:
            selection = input("Select number: ").strip()
            idx = int(selection) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
            if allow_new and idx == len(choices):
                new_value = input("Enter new category name: ").strip()
                if new_value:
                    return new_value
                print("Category name cannot be empty!")
            else:
                print(f"Enter 1..{len(choices) + (1 if allow_new else 0)}")
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(1)


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not response:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print("Enter y or n")


def create_post(
    category: str,
    title: str,
    summary: str = "",
    tags: list[str] | None = None,
    published: bool = True,
    content_body: str = "",
    interactive: bool = False,
) -> int:
    """Create a new post in the database.

    Returns the post ID.
    """
    _ensure_min_env()

    from app import create_app
    from content_sync import create_post as db_create_post
    from models import db

    if tags is None:
        tags = []

    app = create_app()

    with app.app_context():
        if interactive and not category:
            existing = get_existing_categories()
            category = prompt_choice("Select a category:", existing, allow_new=True) if existing else input("Category: ").strip()

        if not category:
            raise ValueError("Category is required")

        if interactive and not title:
            title = input("Enter post title: ").strip()
            if not title:
                raise ValueError("Title is required")

        if interactive and not summary:
            summary = input("Enter post summary (optional): ").strip()

        if interactive and not tags:
            tags_input = input("Enter tags (comma-separated, optional): ").strip()
            if tags_input:
                tags = [t.strip() for t in tags_input.split(",") if t.strip()]

        if not content_body:
            content_body = f"# {title}\n"

        post = db_create_post(
            db.session,
            title=title,
            content_md=content_body,
            category_slug=slugify(category),
            summary=summary,
            tags=[slugify(t) for t in tags],
            published=published,
        )
        db.session.commit()

        print(f"\nPost created in database:")
        print(f"  ID:       {post.id}")
        print(f"  Slug:     {post.slug}")
        print(f"  Title:    {post.title}")
        print(f"  Category: {post.category.slug}")
        print(f"  Tags:     {', '.join(t.slug for t in post.tags) or '(none)'}")
        print(f"  Status:   {'published' if post.published else 'draft'}")

        return post.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new post in the database.")
    parser.add_argument("category", nargs="?", help="Category name")
    parser.add_argument("title", nargs="?", help="Post title")
    parser.add_argument("-s", "--summary", default="", help="Post summary")
    parser.add_argument("-t", "--tags", default="", help="Comma-separated tags")
    parser.add_argument("--draft", action="store_true", help="Create unpublished draft")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--list-categories", action="store_true", help="List categories and exit")
    parser.add_argument("-f", "--file", help="Read content from a markdown file")

    args = parser.parse_args()

    _ensure_min_env()

    if args.list_categories:
        from app import create_app
        app = create_app()
        with app.app_context():
            cats = get_existing_categories()
            print("\nExisting categories:" if cats else "\nNo categories found.")
            for c in cats:
                print(f"  - {c}")
        return

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    if not args.interactive and (not args.category or not args.title):
        parser.error("category and title required (or use -i)")

    content_body = ""
    if args.file:
        fpath = Path(args.file)
        if not fpath.is_file():
            parser.error(f"File not found: {args.file}")
        content_body = fpath.read_text(encoding="utf-8")

    create_post(
        category=args.category or "",
        title=args.title or "",
        summary=args.summary,
        tags=tags,
        published=not args.draft,
        content_body=content_body,
        interactive=args.interactive,
    )


if __name__ == "__main__":
    main()
