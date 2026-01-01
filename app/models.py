from __future__ import annotations

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship

db = SQLAlchemy()

post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)

    posts = relationship("Post", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)

    posts = relationship("Post", secondary=post_tags, back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag {self.slug}>"


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)

    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    title = db.Column(db.String(512), nullable=False, index=True)
    summary = db.Column(db.Text, default="")

    content_md = db.Column(db.Text, nullable=False)
    content_html = db.Column(db.Text, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    category = relationship("Category", back_populates="posts")

    source_path = db.Column(db.String(1024), unique=True, nullable=False, index=True)
    subpath = db.Column(db.String(1024), default="")
    content_sha256 = db.Column(db.String(64), nullable=False, index=True)

    published = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tags = relationship("Tag", secondary=post_tags, back_populates="posts")
    pageviews = relationship("PageView", back_populates="post")

    def __repr__(self) -> str:
        return f"<Post {self.slug}>"


class Visitor(db.Model):
    __tablename__ = "visitors"

    id = db.Column(db.Integer, primary_key=True)
    visitor_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    ip_anon = db.Column(db.String(45), index=True)
    user_agent = db.Column(db.String(512))
    first_seen = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    sessions = relationship("AnalyticsSession", back_populates="visitor")
    pageviews = relationship("PageView", back_populates="visitor")

    def __repr__(self) -> str:
        return f"<Visitor {self.visitor_hash[:8]}>"


class AnalyticsSession(db.Model):
    __tablename__ = "analytics_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id"), nullable=False, index=True)
    visitor = relationship("Visitor", back_populates="sessions")

    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    ended_at = db.Column(db.DateTime, index=True)

    referrer = db.Column(db.String(1024))
    landing_page = db.Column(db.String(512))
    exit_page = db.Column(db.String(512))
    page_count = db.Column(db.Integer, default=0)

    pageviews = relationship("PageView", back_populates="session", order_by="PageView.viewed_at")

    def __repr__(self) -> str:
        return f"<AnalyticsSession {self.session_hash[:8]}>"


class PageView(db.Model):
    __tablename__ = "pageviews"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id"), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("analytics_sessions.id"), index=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), index=True)

    visitor = relationship("Visitor", back_populates="pageviews")
    session = relationship("AnalyticsSession", back_populates="pageviews")
    post = relationship("Post", back_populates="pageviews")

    path = db.Column(db.String(512), nullable=False, index=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    time_on_page = db.Column(db.Integer)

    user_agent = db.Column(db.String(512))
    referrer = db.Column(db.String(1024))
    screen_width = db.Column(db.Integer)
    screen_height = db.Column(db.Integer)

    geo_country_code = db.Column(db.String(2))
    geo_country_name = db.Column(db.String(128))
    geo_city = db.Column(db.String(128))
    geo_region = db.Column(db.String(128))

    def __repr__(self) -> str:
        return f"<PageView {self.path} at {self.viewed_at}>"


class AdminSession(db.Model):
    """Admin authentication sessions via SSH key signatures."""
    __tablename__ = "admin_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_token = db.Column(db.String(128), unique=True, nullable=False, index=True)

    # Keep DB schema compatible with earlier migration (column name is still gpg_fingerprint)
    key_fingerprint = db.Column("gpg_fingerprint", db.String(128), nullable=False)

    challenge = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(512))
    revoked = db.Column(db.Boolean, default=False, index=True)

    def __repr__(self) -> str:
        return f"<AdminSession {self.session_token[:8]} expires {self.expires_at}>"
