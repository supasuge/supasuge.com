# supasuge.com

[www.supasuge.com/](https://supasuge.com/)

A minimal, modular, and secure Flask static site generator style blog serving Markdown posts with production-ready deployment built in.

**NOTE**
> *Incomplete CMS Engine + Theme API*

## Features

- **Markdown-based content** with YAML frontmatter
- **SQLite3 database** (simple, file-based, no separate DB server needed)
- **Automatic content syncing** from filesystem to database
- **Syntax highlighting** via Pygments
- **Secure by default**: XSS protection, CSP headers, HTTPS-only, HSTS
- **Categories and tags** for organizing posts in a manner similar to Hugo and other simple static site generators.
- **Privacy-respecting analytics**
- **SSH key challenge/response authentication** for password-less admin access
- **Production-ready**: Docker, Caddy (automatic HTTPS)

## Tech Stack

- **Backend**: Flask (Python 3.12), SQLAlchemy, Gunicorn
- **Database**: SQLite3
- **Frontend**: Jinja2 templates, vanilla JS/CSS
- **Infrastructure**: Docker Compose, Caddy, Redis
- **Security**: Automatic TLS via Caddy/ACME, rate limiting, CSRF protection

## Quick Start

```bash
# Clone repository
git clone <repo-url>
cd vps.com/app

# Configure environment
cp .env.example .env
./scripts/gensecrets.sh

# Edit .env with your settings
nano .env

# Start with Docker
docker compose up -d

# Or run locally (development)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Documentation

- **[Setup Guide](docs/SETUP.md)** - Initial setup and configuration
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Development Guide](docs/DEVELOPMENT.md)** - Local development workflow
- **[Certificate Management](docs/CERTIFICATES.md)** - SSL/TLS certificates (legacy; Caddy handles this automatically now)
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Cleanup Checklist](docs/CLEANUP_CHECKLIST.md)** - Project cleanup tasks

## Deployment (Explicit Steps)

The script-driven deployment workflow is:

```bash
# 1) From your local machine
cd /home/supasuge/Documents/Projects/vps.com
```

```bash
# 2) Stage a clean local archive
rm -f supa*.tar* supasuge.tar.xz
tar -cvJf supasuge.tar.xz vps.com
```

```bash
# 3) Run the deployment CLI (build + upload + backup + promote + fix perms + rebuild/start)
python3 supasuge_deploy_cli_v2.py remote-deploy \
  --archive-name supasuge.tar.xz \
  --extract-root "~/"
```

The command above will:

1. Upload the archive to the remote host over SSH.
2. Create a remote DB backup (`.sqlite.xz`) and copy it back to the local host.
3. Stop the current compose stack.
4. Promote the new release.
5. Resolve and run `fixperms.sh` as `appuser`.
6. Rebuild and start containers with `docker compose build --no-cache` and `docker compose up -d`.

If you need the old staged workflow broken into explicit remote commands, run:

```bash
# 1) Upload archive manually
scp -i ~/.ssh/id_ed25519 -P 2222 supasuge.tar.xz appuser@vps.com:~/
```

```bash
# 2) On remote host, extract and run permissions script
ssh -i ~/.ssh/id_ed25519 -p 2222 appuser@vps.com \
  'mkdir -p ~/vps.com && tar -xJf ~/vps.tar.xz -C ~/'
ssh -i ~/.ssh/id_ed25519 -p 2222 appuser@vps.com \
  'sudo chown -R $USER:$USER vps.com && sudo chown -R 10001:10001 vps.com/app/content && sudo chown -R 775 vps.com/app/content'
```
Obviously, replace `vps.com` and `vps.tar.xz` with your own directory archive to speed up upload time.

```bash
# 3) Backup DB, stop stack, then rebuild with no cache
python3 supasuge_deploy_cli_v2.py remote-deploy \
  --archive-name supasuge.tar.xz \
  --db-backup \
  --local-backup-dir ./deploy-backups \
  --extract-root "~/"

# or run just the stack part manually
ssh -i ~/.ssh/id_ed25519 -p 2222 appuser@vps.com \
  'cd ~/vps.com/app && docker compose down'
ssh -i ~/.ssh/id_ed25519 -p 2222 appuser@vps.com \
  'cd ~/vps.com/app && docker compose build --no-cache && docker compose up -d'
```

Use the local DB volume helper if you only need to replace SQLite data:

```bash
./app/scripts/sync-db-volume.sh --yes
```

Useful checks after deployment:

```bash
ssh -i ~/.ssh/id_ed25519 -p 2222 appuser@vps.com \
  'cd ~/vps.com/app && docker compose ps && docker compose logs --tail=80'
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
    │   └── crypto.md
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
| `content/articles/ctf/crypto.md` | `ctf` | `challenges/crypto.md` |

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
- Set `LOCAL_DEV=0`
- Use a proper `SECRET_KEY` (generate with `./scripts/gensecrets.sh`)
- Enable `COOKIE_SECURE=1` (HTTPS)
- Enable `ENABLE_HSTS=1` (HTTPS)
- Configure `BEHIND_PROXY=1` if behind a reverse proxy (Caddy, nginx, etc.)
- SQLite3 database (default configuration)

## Configuration

All configuration is via **environment variables** (see `.env` or `config.py`).

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SITE_NAME` | `Evan Pardon's Portfolio` | Site name (in templates) |
| `SITE_URL` | `https://vps.com` | Canonical URL |
| `SECRET_KEY` | (required) | Flask secret key (use `./scripts/gensecrets.sh`) |
| `DATABASE_URL` | `sqlite:///instance/blog.db` | SQLAlchemy connection string (SQLite3) |
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


> Be careful with `chmod 777` - it grants full access to everyone!

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

- Verify database file exists: `ls -la instance/blog.db`
- Check DATABASE_URL in `.env` (should be SQLite)
- Run migrations: `alembic upgrade head`
- Check file permissions on instance/ directory

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

This is a **personal blog**. It should be easy to understand.

---

## Changelog

### 2026-03-15: Architecture & Admin Overhaul

#### Caddy Reverse Proxy (replaces Nginx + Certbot)

- **Replaced Nginx + Certbot** with [Caddy](https://caddyserver.com/) in `docker-compose.yml`
- Caddy handles TLS certificate provisioning automatically via ACME (no manual cert scripts)
- Added HTTP/3 (QUIC) support via `443/udp` port mapping
- **Removed**: `nginx/` config directory, `obtain-certs.sh`, `renew-certs.sh` (moved to `scripts/archive/`)
- **Updated**: `sitectl.sh` and `deploy-production.sh` for Caddy commands (`caddy-validate`, `caddy-reload`)
- Caddyfile lives at project root, mounted into the container

#### Content Archive Pipeline (DB as single source of truth)

- **New module**: `content_archive.py` — archives synced `.md` files into `instance/content_archive.tar.gz`
- After `sync_content()` succeeds, source `.md` files are appended to a tar.gz archive with a JSON manifest (`instance/content_manifest.json`) recording SHA256, original path, timestamp, and file size
- Source `.md` files are deleted from disk after archival
- Post editing (`save_post_content`, `save_post_metadata`) is now **DB-only** — no longer requires source files on disk
- The archive serves as an audit trail / backup; the database is the runtime source of truth

#### SSH Signature Parsing Hardening

- **New function**: `normalize_ssh_signature()` in `auth/ssh_auth.py`
  - Handles CRLF line endings from Windows/browser paste
  - Extracts signature block from surrounding text (terminal prompts, filenames)
  - Strips trailing whitespace per line
  - Validates structure before passing to `ssh-keygen`
  - Returns clear error messages for each failure mode
- Signature verification now uses the normalized output instead of raw paste

#### Bug Fixes

- Fixed `import secret` → `import secrets` in `app.py` (was crashing CSP nonce generation)
- Replaced all `datetime.utcnow()` calls with `datetime.now(UTC)` across:
  - `auth/ssh_auth.py`
  - `blueprints/admin/auth.py`
  - `models.py` (all column defaults)
- Post content/metadata editing no longer fails silently when source `.md` is missing

#### UI/UX Polish

- **Admin navigation**: Sticky header with backdrop blur, tighter spacing, smaller font sizes
- **Flash messages**: Auto-dismiss after 5 seconds with a progress bar animation and smooth slide-out
- **Login page**: Full redesign with proper centered layout, glass-morphism card, responsive scaling
- **Tables**: Rounded corners, separate border-spacing, subtler hover states
- **Buttons**: Cubic-bezier transitions, active press feedback (`scale(0.97)`), hover glow on primary
- **Cards**: Smoother hover lift with box-shadow, reduced border opacity
- **Responsive**: Admin nav wraps on mobile, stats grid collapses to single column, table cells resize
- **Typography**: Tighter letter-spacing on headings, tabular-nums on numeric data

#### Files Removed / Archived

| File | Action | Reason |
|------|--------|--------|
| `scripts/obtain-certs.sh` | Moved to `scripts/archive/` | Caddy handles ACME automatically |
| `scripts/renew-certs.sh` | Moved to `scripts/archive/` | Caddy handles renewal automatically |
