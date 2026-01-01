#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from security import slugify

TEMPLATE = """---
title: "{title}"
summary: "{summary}"
tags: [{tags}]
published: {published}
date: {date}
---

# {title}

{summary}

## Content

Write your content here.
"""


def get_existing_categories(content_dir: Path) -> list[str]:
    if not content_dir.exists():
        return []
    categories = []
    for item in content_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            categories.append(item.name)
    return sorted(categories)


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


def register_in_database(content_dir: Path, verbose: bool = True) -> dict:
    """
    Best-effort sync: uses your app's Config/DATABASE_URL if available.
    If DATABASE_URL isn't set, we skip rather than pretending sqlite exists.
    """
    try:
        from content_sync import sync_content
        from models import db
        from app import create_app
        from config import Config

        if not os.getenv("DATABASE_URL"):
            if verbose:
                print("\n⚠️  DATABASE_URL not set, skipping DB sync.")
            return {}

        app = create_app()
        cfg = Config()

        with app.app_context():
            results = sync_content(str(content_dir), db.session)

        if verbose:
            print("\n✓ Database sync completed:")
            print(f"  Created: {results.get('created', 0)}")
            print(f"  Updated: {results.get('updated', 0)}")
            print(f"  Total indexed: {results.get('total_indexed', 0)}")

        return results

    except Exception as e:
        if verbose:
            print(f"\n⚠️  Error during database sync: {e}")
        return {}


def create_post(
    category: str,
    title: str,
    summary: str = "",
    tags: list[str] = None,
    published: bool = True,
    subdir: str = "",
    content_dir: Optional[Path] = None,
    interactive: bool = False,
    sync_db: bool = False,
    open_editor: bool = False,
) -> Path:
    if content_dir is None:
        content_dir = Path(__file__).parent.parent / "content" / "articles"
    if tags is None:
        tags = []

    if interactive and not category:
        existing = get_existing_categories(content_dir)
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

    category_slug = slugify(category)
    title_slug = slugify(title)
    tag_slugs = [slugify(t) for t in tags]
    tags_str = ", ".join(f'"{t}"' for t in tag_slugs)

    target_dir = content_dir / category_slug / (subdir.strip("/") if subdir else "")
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{title_slug}.md"

    if file_path.exists():
        raise FileExistsError(f"File already exists: {file_path}")

    content = textwrap.dedent(TEMPLATE.format(
        title=title,
        summary=summary,
        tags=tags_str,
        published=str(published).lower(),
        date=date.today().isoformat(),
    ))

    file_path.write_text(content, encoding="utf-8")
    print(f"\n✓ Created: {file_path}")

    if sync_db or (interactive and prompt_yes_no("\nRegister post in database?", default=True)):
        register_in_database(content_dir, verbose=True)

    if open_editor or (interactive and prompt_yes_no("\nOpen in editor?", default=True)):
        editor = os.environ.get("EDITOR", "nano")
        subprocess.run([editor, str(file_path)], check=False)

    return file_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new markdown post.")
    parser.add_argument("category", nargs="?", help="Category name")
    parser.add_argument("title", nargs="?", help="Post title")
    parser.add_argument("-s", "--summary", default="", help="Post summary")
    parser.add_argument("-t", "--tags", default="", help="Comma-separated tags")
    parser.add_argument("--subdir", default="", help="Subdirectory under category")
    parser.add_argument("--draft", action="store_true", help="Create unpublished draft")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--sync", action="store_true", help="Register in database after creation")
    parser.add_argument("--no-open", action="store_true", help="Don't open in editor")
    parser.add_argument("--list-categories", action="store_true", help="List categories and exit")

    args = parser.parse_args()
    content_dir = Path(__file__).parent.parent / "content" / "articles"

    if args.list_categories:
        cats = get_existing_categories(content_dir)
        print("\nExisting categories:" if cats else "\nNo categories found.")
        for c in cats:
            print(f"  • {c}")
        return

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    if not args.interactive and (not args.category or not args.title):
        parser.error("category and title required (or use -i)")

    create_post(
        category=args.category or "",
        title=args.title or "",
        summary=args.summary,
        tags=tags,
        published=not args.draft,
        subdir=args.subdir,
        content_dir=content_dir,
        interactive=args.interactive,
        sync_db=args.sync,
        open_editor=not args.no_open,
    )


if __name__ == "__main__":
    main()
