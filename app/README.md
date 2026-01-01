# Personal Blog

A minimal, secure Flask-based blog for serving Markdown posts as HTML.

## Deployment


- Syncing content placed into `/content/articles/`, categories included.
```bash
docker compose run --rm web python scripts/sync.py
```

On host (requires `DATABASE_URL` to point to localhost:3306): 
- `python scripts/sync.py`







## Features

- Markdown-based content with YAML frontmatter
- MySQL database with SQLAlchemy ORM
- Automatic content syncing from filesystem to database (`/content/articles/*`)
- Syntax highlighting via `Pygments`
- Secure by default (XSS protection, CSP headers, HTML sanitization)
- Category and tag support
- Analytics tracking (privacy-respecting)
- SSH key challenge-response authentication

## Tech Stack

- **Python 3.12**
- **Flask** - Web framework
- **SQLAlchemy** - ORM
- **MySQL** - Database
- **Alembic** - Database migrations
- **Bleach** - HTML sanitization
- **python-frontmatter** - Metadata parsing
- **Pygments** - Syntax highlighting

## Requirements

- `Python 3.12+`
- `MySQL 8.0+`
- `Flask`
- `Redis + Flask-Limiter (for rate limiting)`

## Installation

1. Clone the repository
2. Install dependencies: admin

```bash
pip install -e .
```

3. Set up environment variables in `.env`:

```bash
SECRET_KEY=your-secret-key-here
DATABASE_URL=mysql+mysqlconnector://user:password@localhost/dbname
SITE_NAME=My Blog
SITE_URL=https://yourdomain.com
CONTENT_DIR=content/articles
RATELIMIT_STORAGE_URL=redis://localhost:6379/0
```

4. Initialize the database:

```bash
alembic upgrade head
```

5. Run the application:

```bash
python app.py
```

## Directory Structure

```
.
├── app.py                  # Flask app + initialization
├── config.py               # Environment-driven config
├── models.py               # SQLAlchemy models
├── content_sync.py         # Markdown → DB sync
├── content_indexer.py      # Markdown rendering & highlighting
├── security.py             # Security utilities (slugify, etc.)
├── blueprints/             # Flask blueprints
│   ├── public/             # Public routes
│   ├── api/                # API endpoints
│   └── admin/              # Admin routes
├── content/                # Your blog content (see below)
│   └── articles/           # Main content directory
│       ├── linux/          # Category: linux
│       ├── ctf/            # Category: ctf
│       ├── guides/         # Category: guides
│       └── ...             # More categories
├── templates/              # Jinja2 templates
├── static/                 # CSS, JS, images
├── public/                 # robots.txt, security.txt
├── migrations/             # Alembic migrations
└── keys/admin_ssh.pub      # SSH public key for admin auth
```

## Content Organization

### Directory Structure

Content is organized in a **two-level hierarchy**:

```
content/
└── articles/                    # Root (configured via CONTENT_DIR)
    ├── linux/                   # Category = "linux"
    │   └── hello-world.md
    ├── ctf/                     # Category = "ctf"
    │   ├── writeup-2024.md
    │   └── challenges/          # Subcategory support
    │       └── crypto.md
    └── guides/                  # Category = "guides"
        └── getting-started.md
```

**Category derivation rules:**
- The **first directory** under `content/articles/` becomes the category
- Files directly in `content/articles/` → category: `general`
- Nested subdirectories are preserved as `subpath` metadata

### Examples

| File Path | Category | Subpath |
|-----------|----------|---------|
| `content/articles/hello.md` | `general` | `hello.md` |
| `content/articles/linux/intro.md` | `linux` | `intro.md` |
| `content/articles/ctf/challenges/crypto.md` | `ctf` | `challenges/crypto.md` |

## Adding a New Post

### 1. Create the Markdown File

Create a new `.md` file in the appropriate category directory:

```bash
# Example: Create a post in the "linux" category
touch content/articles/linux/my-new-post.md
```

### 2. Add Frontmatter

Every post **must** begin with YAML frontmatter between `---` delimiters.

#### Required Fields

Only the content itself is truly required - all metadata fields have defaults.

#### Optional Fields

All frontmatter fields are optional, but recommended for proper display:

```yaml
---
title: "Your Post Title"
summary: "A brief description of your post (recommended for listings)"
tags: ["tag1", "tag2", "tag3"]
published: true
date: 2024-12-25T10:30:00Z
slug: custom-url-slug
---
```

### Frontmatter Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | No | Filename stem | Post title (displayed in listings and post page) |
| `summary` | string | No | `""` | Brief description (for listings, meta tags) |
| `tags` | list[string] | No | `[]` | List of tags (auto-slugified) |
| `published` | boolean | No | `true` | Whether post is visible |
| `date` | ISO 8601 | No | `null` | Publication date |
| `slug` | string | No | Slugified title | URL slug (auto-generated from title if omitted) |

#### Field Details

**`title`** (string)
- Displayed as the post heading
- Used to generate the slug if `slug` is not provided
- If omitted, uses the filename (without `.md` extension)

**`summary`** (string)
- Shown in post listings
- Used for meta description tags
- Can be empty

**`tags`** (list of strings)
- Each tag is automatically slugified (lowercase, hyphens)
- Example: `"Machine Learning"` → `machine-learning`
- Tags are stored as separate entities in the database
- Multiple posts can share tags

**`published`** (boolean)
- `true` (default): Post is visible
- `false`: Post is hidden from listings
- Useful for drafts

**`date`** (ISO 8601 datetime string)
- Optional publication date
- Format: `YYYY-MM-DDTHH:MM:SSZ` or `YYYY-MM-DD`
- Examples:
  - `2024-12-25T10:30:00Z`
  - `2024-12-25`
- If omitted, no date is stored (can use `created_at` instead)

**`slug`** (string)
- Custom URL-safe identifier
- Must be unique across all posts
- Auto-generated from `title` if omitted
- Slugification rules:
  - Lowercase
  - Spaces → hyphens
  - Special chars removed
  - Unicode normalized

### 3. Write Content

Write your post content in Markdown **after** the closing `---`:

```markdown
---
title: "Getting Started with Linux"
summary: "A beginner's guide to Linux commands"
tags: ["linux", "tutorial", "beginner"]
published: true
date: 2024-12-25
---

# Getting Started with Linux

This guide covers the basics of Linux command line.

## Basic Commands

Here are some essential commands:

```bash
ls -la        # List files
cd /path      # Change directory
pwd           # Print working directory
```

## File Permissions

Linux uses a permission system...
```

### 4. Sync to Database

The app automatically syncs content on startup if `AUTO_SYNC_ON_START=1` (default).

**Manual sync:**
```python
from app import create_app
from content_sync import sync_content
from config import Config
from models import db

app = create_app()
with app.app_context():
    cfg = Config()
    result = sync_content(cfg.CONTENT_DIR, db.session)
    print(f"Created: {result['created']}, Updated: {result['updated']}, Deleted: {result['deleted']}")
```

**Sync behavior:**
- New files → Creates database records
- Modified files → Updates existing records (detected via SHA256 hash)
- Deleted files → Removes database records
- Renamed files → Treated as delete + create

## Markdown Features

### Supported Extensions

The blog uses Python-Markdown with these extensions enabled:

- `fenced_code` - Code blocks with syntax highlighting
- `codehilite` - Pygments integration
- `tables` - GFM-style tables
- `toc` - Table of contents generation
- `admonition` - Note/warning boxes

### Code Highlighting

Syntax highlighting is automatic for fenced code blocks:

````markdown
```python
def hello():
    print("Hello, world!")
```
````

Supported languages: Python, Bash, JavaScript, Go, Rust, C, C++, Java, and [100+ more](https://pygments.org/languages/).

### Math Support

The example post shows MathJax usage:

```markdown
Inline math: $a^2 + b^2 = c^2$

Block math:
$$
E(\mathbb{F}_p):\quad y^2 \equiv x^3 + ax + b \pmod p
$$
```

**Note:** Ensure your CSP allows MathJax CDN (see `config.py`).

### Tables

```markdown
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

### Admonitions

```markdown
!!! note "Optional Title"
    This is a note admonition.

!!! warning
    This is a warning.
```

## Security

### HTML Sanitization

All Markdown is rendered to HTML and **sanitized via Bleach**:

- Only safe tags allowed: `p`, `a`, `pre`, `code`, `h1-h6`, `ul`, `ol`, `li`, `table`, etc.
- Only safe attributes: `href`, `src`, `class`, `alt`, `title`
- Only safe protocols: `http`, `https`, `mailto`, `data`
- JavaScript event handlers **stripped**
- Inline `<script>` tags **removed**

**This prevents stored XSS attacks.**

### Allowed HTML Tags

See `content_indexer.py:24-35` for the complete allowlist:

```python
ALLOWED_TAGS = {
    "p", "pre", "code", "span",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "br",
    "ul", "ol", "li",
    "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "img", "div", "a", "b", "i", "strong", "em"
}
```

### Security Headers

Set automatically on every response (see `app.py:106-121`):

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Content-Security-Policy` (configurable via env)
- `Strict-Transport-Security` (when HTTPS enabled)

### Database Security

- **No raw SQL** - All queries via SQLAlchemy ORM
- **No `.execute(text())`** - Prevents SQL injection
- **Parameterized queries only**

## Database Migrations

Managed via **Alembic**.

### Create a Migration

After modifying `models.py`:

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply Migrations

```bash
alembic upgrade head
```

### Rollback

```bash
alembic downgrade -1    # Go back one migration
alembic downgrade base  # Reset to initial state
```

**IMPORTANT:** Never use `db.create_all()` in production.

## Running the Application

### Development

```bash
export FLASK_DEBUG=1
python app.py
```

Visit: `http://localhost:5000`

### Production

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

**Requirements:**
- Set `FLASK_DEBUG=0`
- Use a proper `SECRET_KEY`
- Enable `COOKIE_SECURE=1` (HTTPS)
- Enable `ENABLE_HSTS=1` (HTTPS)
- Configure `BEHIND_PROXY=1` if using nginx/Apache
- Use MySQL, not SQLite

## Configuration

All configuration is via **environment variables** (see `.env` or `config.py`).

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SITE_NAME` | `My Site` | Site name (in templates) |
| `SITE_URL` | `https://example.com` | Canonical URL |
| `SECRET_KEY` | `dev-change-me` | Flask secret key (CHANGE IN PRODUCTION) |
| `DATABASE_URL` | `sqlite:///site.db` | SQLAlchemy connection string |
| `CONTENT_DIR` | `content/articles` | Directory containing Markdown files |

### Security Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `COOKIE_SECURE` | `1` | Require HTTPS for cookies |
| `COOKIE_SAMESITE` | `Lax` | SameSite cookie policy |
| `ENABLE_HSTS` | `1` | Enable HTTP Strict Transport Security |
| `CSP` | (see config.py) | Content Security Policy |
| `ALLOWED_HOSTS` | `""` | Comma-separated allowed Host headers |

### Proxy Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `BEHIND_PROXY` | `1` | Enable ProxyFix middleware |
| `PROXY_FIX_X_FOR` | `1` | Trust X-Forwarded-For header depth |
| `PROXY_FIX_X_PROTO` | `1` | Trust X-Forwarded-Proto header depth |
| `PROXY_FIX_X_HOST` | `1` | Trust X-Forwarded-Host header depth |

### Sync Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_SYNC_ON_START` | `1` | Sync content on app startup |

### Admin Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_GPG_KEY_PATH` | `keys/admin.asc` | Path to admin GPG public key |
| `ADMIN_SESSION_TIMEOUT` | `28800` | Session timeout in seconds (8 hours) |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATELIMIT_STORAGE_URL` | `redis://redis:6379/0` | Redis URL for rate limiting |
| `RATELIMIT_DEFAULT` | `300/hour` | Default rate limit |

## Common Tasks

### Add a New Post

1. Create `content/articles/category/post-name.md`
2. Add frontmatter (title, summary, tags, etc.)
3. Write content in Markdown
4. Restart app (or wait for auto-sync)

### Change a Post's Category

Move the file to a different category directory:

```bash
mv content/articles/old-category/post.md content/articles/new-category/post.md
```

Restart the app to sync changes.

### Hide a Draft

Set `published: false` in frontmatter:

```yaml
---
title: "Work in Progress"
published: false
---
```

### Delete a Post

Remove the `.md` file and restart the app. The database record will be automatically deleted.

### Custom URL Slug

Specify a `slug` in frontmatter:

```yaml
---
title: "My Amazing Post"
slug: amazing-post
---
```

URL: `/posts/amazing-post`

## Example Post Template

```markdown
---
title: "Understanding Linux Permissions"
summary: "A comprehensive guide to file permissions in Linux"
tags: ["linux", "security", "sysadmin"]
published: true
date: 2024-12-25T15:00:00Z
---

# Understanding Linux Permissions

Linux uses a permission model to control file access...

## Permission Types

There are three types of permissions:

- **Read (r)**: View file contents
- **Write (w)**: Modify file contents
- **Execute (x)**: Run file as program

## Checking Permissions

```bash
ls -l /path/to/file
```

Output explained:

```
-rw-r--r-- 1 user group 1234 Dec 25 15:00 file.txt
```

## Changing Permissions

```bash
chmod 644 file.txt
chmod u+x script.sh
```

!!! warning
    Be careful with `chmod 777` - it grants full access to everyone!

## Summary

Understanding permissions is crucial for Linux security...

## Troubleshooting

### Posts not showing up

- Check `published: true` in frontmatter
- Verify file is in correct directory structure
- Check logs for sync errors
- Run manual sync (see "Sync to Database" section)

### Syntax highlighting not working

- Ensure language is specified in code fence: ` ```python `
- Verify Pygments supports the language
- Check that `pygments_css()` is loaded in template

### Database errors

- Verify MySQL is running: `systemctl status mysql`
- Check connection string in `DATABASE_URL`
- Run migrations: `alembic upgrade head`
- Check permissions on database user

### Rate limiting issues

- Verify Redis is running: `redis-cli ping`
- Check `RATELIMIT_STORAGE_URL` is correct
- For local dev, use: `RATELIMIT_STORAGE_URL=memory://`

## Design Philosophy

This project prioritizes:

1. **Security** over convenience
2. **Simplicity** over features
3. **Readability** over cleverness
4. **Stability** over cutting-edge tech

**What this is NOT:**
- A SaaS platform
- A multi-tenant system
- A CMS with a GUI
- A framework

This is a **personal blog**. It should be easy to understand in 6 months.

## License

Personal project - all rights reserved (or specify your license).

## Contributing

This is a personal blog system, but feedback and suggestions are welcome.
