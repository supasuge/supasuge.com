"""Shared test fixtures for the blog application."""

import importlib
import importlib.util
import os

import pytest

# Set test environment before any app imports
# Keys must pass _validate_secret: min 48 chars, no weak substrings
os.environ["LOCAL_DEV"] = "1"
os.environ["SECRET_KEY"] = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6xxxx"
os.environ["ANALYTICS_SALT"] = "x9y8z7w6v5u4x9y8z7w6v5u4x9y8z7w6"
os.environ["AUTO_SYNC_CONTENT"] = "0"

# Import app.py (the module) directly since __init__.py shadows it
_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("app_module", os.path.join(_app_dir, "app.py"))
_app_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_app_mod)
create_app = _app_mod.create_app

from config import DevelopmentConfig
from models import (
    AdminSession, AnalyticsSession, AuthChallenge,
    Category, PageView, Post, Tag, Visitor,
    db as _db, post_tags,
)


@pytest.fixture(scope="session")
def app():
    """Create application for testing with a temp SQLite database."""
    cfg = DevelopmentConfig()
    test_app = create_app(config=cfg)
    test_app.config["TESTING"] = True
    test_app.config["WTF_CSRF_ENABLED"] = False
    test_app.config["ANALYTICS_ENABLED"] = False
    test_app.config["GEOIP_DB_PATH"] = ""

    with test_app.app_context():
        _db.create_all()

    yield test_app


@pytest.fixture(autouse=True)
def clean_db(app):
    """Clean all tables after each test for isolation."""
    yield
    with app.app_context():
        # Delete in dependency order
        _db.session.execute(post_tags.delete())
        for model in [PageView, AnalyticsSession, Visitor, AdminSession, AuthChallenge, Post, Tag, Category]:
            _db.session.query(model).delete()
        _db.session.commit()


@pytest.fixture
def db_session(app):
    """Provide the db session within app context."""
    with app.app_context():
        yield _db.session


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


class _Ref:
    """Plain data holder to avoid SQLAlchemy DetachedInstanceError."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def sample_category(app):
    """Create a sample category, return a plain ref."""
    with app.app_context():
        cat = Category(slug="ctf", name="CTF")
        _db.session.add(cat)
        _db.session.commit()
        return _Ref(id=cat.id, slug=cat.slug, name=cat.name)


@pytest.fixture
def sample_tag(app):
    """Create a sample tag, return a plain ref."""
    with app.app_context():
        tag = Tag(slug="crypto", name="Crypto")
        _db.session.add(tag)
        _db.session.commit()
        return _Ref(id=tag.id, slug=tag.slug, name=tag.name)


@pytest.fixture
def sample_post(app, sample_category, sample_tag, tmp_path):
    """Create a sample published post with a source file on disk."""
    md_file = tmp_path / "test-post.md"
    md_file.write_text(
        "---\ntitle: Test Post\nsummary: A test\ntags: [crypto]\npublished: true\n---\n\nHello world\n",
        encoding="utf-8",
    )

    with app.app_context():
        post = Post(
            slug="test-post",
            title="Test Post",
            summary="A test",
            content_md="Hello world",
            content_html="<p>Hello world</p>",
            content_sha256="abc123",
            category_id=sample_category.id,
            source_path=str(md_file),
            published=True,
        )
        _db.session.add(post)
        _db.session.flush()
        post.tags.append(_db.session.get(Tag, sample_tag.id))
        _db.session.commit()
        return _Ref(
            id=post.id, slug=post.slug, title="Test Post",
            source_path=str(md_file), published=True,
        )


@pytest.fixture
def unpublished_post(app, sample_category, tmp_path):
    """Create an unpublished/draft post."""
    md_file = tmp_path / "draft-post.md"
    md_file.write_text(
        "---\ntitle: Draft Post\npublished: false\n---\n\nDraft content\n",
        encoding="utf-8",
    )

    with app.app_context():
        post = Post(
            slug="draft-post",
            title="Draft Post",
            summary="",
            content_md="Draft content",
            content_html="<p>Draft content</p>",
            content_sha256="def456",
            category_id=sample_category.id,
            source_path=str(md_file),
            published=False,
        )
        _db.session.add(post)
        _db.session.commit()
        return _Ref(
            id=post.id, slug=post.slug, title="Draft Post",
            source_path=str(md_file), published=False,
        )
