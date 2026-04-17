"""Analytics service for visitor tracking with privacy-first design and GeoIP."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import Any, Optional

import geoip2.database
import geoip2.errors
from flask import current_app
from sqlalchemy import func
from models import AnalyticsSession, PageView, Post, Visitor, db


def anonymize_ip(ip: str) -> str:
    if not ip:
        return "0.0.0.0"

    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3]) + "::"

    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".0"

    return "0.0.0.0"


def lookup_geoip(ip: str) -> dict[str, str]:
    db_path = current_app.config.get("GEOIP_DB_PATH")

    if not db_path or not os.path.exists(db_path):
        current_app.logger.warning(f"GeoIP database not found at {db_path}")
        return {"country_code": "", "country_name": "", "city": "", "region": ""}

    try:
        with geoip2.database.Reader(db_path) as reader:
            response = reader.city(ip)
            return {
                "country_code": response.country.iso_code or "",
                "country_name": response.country.name or "",
                "city": response.city.name or "",
                "region": response.subdivisions.most_specific.name or "",
            }
    except (geoip2.errors.AddressNotFoundError, ValueError) as e:
        current_app.logger.debug(f"GeoIP lookup failed for {ip}: {e}")
        return {"country_code": "", "country_name": "", "city": "", "region": ""}


def _iso_date(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def get_or_create_visitor(visitor_hash: str, ip_address: str, user_agent: str) -> Visitor:
    """
    Visitor identity is provided by the client (visitor_hash is a stable ID cookie).
    We still store a masked IP for basic operational debugging, not identity.
    """
    try:
        visitor = db.session.query(Visitor).filter_by(visitor_hash=visitor_hash).one_or_none()
        if visitor:
            visitor.last_seen = datetime.now(UTC)
            db.session.commit()
            return visitor

        visitor = Visitor(
            visitor_hash=visitor_hash,
            ip_anon=anonymize_ip(ip_address),
            user_agent=(user_agent or "")[:512],
        )
        db.session.add(visitor)
        db.session.commit()
        return visitor

    except Exception as e:
        current_app.logger.error(f"Error in get_or_create_visitor: {e}")
        db.session.rollback()
        raise


def get_or_create_session(session_hash: str, visitor: Visitor, referrer: str, landing_page: str) -> AnalyticsSession:
    """
    IMPORTANT:
    AnalyticsSession.session_hash is UNIQUE in your model.
    So we cannot "create a new session with the same session_hash" on timeout.
    Instead, if the session is expired, we close it and re-use the same row as a new session window.
    """
    try:
        session = db.session.query(AnalyticsSession).filter_by(session_hash=session_hash).one_or_none()
        timeout_seconds = int(current_app.config.get("ANALYTICS_SESSION_TIMEOUT", 1800))
        now = datetime.now(UTC)

        if session:
            # If timed out, restart the session window (reuse same unique session_hash row).
            if session.last_activity and (now - session.last_activity) > timedelta(seconds=timeout_seconds):
                session.started_at = now
                session.last_activity = now
                session.ended_at = None
                session.page_count = 0
                session.landing_page = (landing_page or "")[:512]
                session.exit_page = None
                session.referrer = referrer[:1024] if referrer else None
                db.session.commit()
                return session

            # still active
            session.last_activity = now
            session.exit_page = (landing_page or "")[:512]
            db.session.commit()
            return session

        # brand new
        session = AnalyticsSession(
            session_hash=session_hash,
            visitor_id=visitor.id,
            referrer=referrer[:1024] if referrer else None,
            landing_page=(landing_page or "")[:512],
            started_at=now,
            last_activity=now,
            page_count=0,
        )
        db.session.add(session)
        db.session.commit()
        return session

    except Exception as e:
        current_app.logger.error(f"Error in get_or_create_session: {e}")
        db.session.rollback()
        raise


def record_pageview(
    path: str,
    visitor_hash: str,
    session_hash: str,
    referrer: Optional[str],
    user_agent: str,
    ip_address: str,
    screen_dims: Optional[dict[str, int]] = None,
    post_id: Optional[int] = None,
) -> PageView:
    try:
        visitor = get_or_create_visitor(visitor_hash, ip_address, user_agent)
        session = get_or_create_session(session_hash, visitor, referrer or "", path)

        session.page_count = int(session.page_count or 0) + 1
        session.exit_page = (path or "")[:512]

        geo = lookup_geoip(ip_address)

        post = None
        if post_id:
            post = db.session.query(Post).filter_by(id=post_id).one_or_none()

        pageview = PageView(
            visitor_id=visitor.id,
            session_id=session.id,
            post_id=post.id if post else None,
            path=(path or "")[:512],
            user_agent=(user_agent or "")[:512],
            referrer=referrer[:1024] if referrer else None,
            screen_width=screen_dims.get("width") if screen_dims else None,
            screen_height=screen_dims.get("height") if screen_dims else None,
            geo_country_code=geo["country_code"],
            geo_country_name=geo["country_name"],
            geo_city=geo["city"],
            geo_region=geo["region"],
            time_on_page=0,  # <- critical: don't leave NULL
        )

        db.session.add(pageview)
        db.session.commit()
        return pageview

    except Exception as e:
        current_app.logger.error(f"Error recording pageview for {path}: {e}")
        db.session.rollback()
        raise


def get_analytics_summary(days: int = 30) -> dict[str, Any]:
    try:
        cutoff = datetime.now(UTC) - timedelta(days=days)

        total_views = (
            db.session.query(func.count(PageView.id))
            .filter(PageView.viewed_at >= cutoff)
            .scalar()
        ) or 0

        unique_visitors = (
            db.session.query(func.count(func.distinct(PageView.visitor_id)))
            .filter(PageView.viewed_at >= cutoff)
            .scalar()
        ) or 0

        top_posts_rows = (
            db.session.query(Post.title, func.count(PageView.id).label("views"))
            .join(PageView, PageView.post_id == Post.id)
            .filter(PageView.viewed_at >= cutoff)
            .group_by(Post.id, Post.title)
            .order_by(func.count(PageView.id).desc())
            .limit(10)
            .all()
        )
        top_posts = [(str(r[0]), int(r[1])) for r in top_posts_rows]

        top_ref_rows = (
            db.session.query(PageView.referrer, func.count(PageView.id).label("count"))
            .filter(
                PageView.viewed_at >= cutoff,
                PageView.referrer.isnot(None),
                PageView.referrer != "",
            )
            .group_by(PageView.referrer)
            .order_by(func.count(PageView.id).desc())
            .limit(10)
            .all()
        )
        top_referrers = [(str(r[0]), int(r[1])) for r in top_ref_rows]

        top_country_rows = (
            db.session.query(PageView.geo_country_name, func.count(PageView.id).label("count"))
            .filter(
                PageView.viewed_at >= cutoff,
                PageView.geo_country_name.isnot(None),
                PageView.geo_country_name != "",
            )
            .group_by(PageView.geo_country_name)
            .order_by(func.count(PageView.id).desc())
            .limit(10)
            .all()
        )
        top_countries = [(str(r[0]), int(r[1])) for r in top_country_rows]

        daily_rows = (
            db.session.query(
                func.date(PageView.viewed_at).label("date"),
                func.count(PageView.id).label("count"),
            )
            .filter(PageView.viewed_at >= cutoff)
            .group_by(func.date(PageView.viewed_at))
            .order_by(func.date(PageView.viewed_at))
            .all()
        )
        daily_views = [[_iso_date(r[0]), int(r[1])] for r in daily_rows]

        return {
            "total_views": int(total_views),
            "unique_visitors": int(unique_visitors),
            "top_posts": top_posts,
            "top_referrers": top_referrers,
            "top_countries": top_countries,
            "daily_views": daily_views,
        }

    except Exception as e:
        current_app.logger.error(f"Error in get_analytics_summary: {e}")
        return {
            "total_views": 0,
            "unique_visitors": 0,
            "top_posts": [],
            "top_referrers": [],
            "top_countries": [],
            "daily_views": [],
        }


def get_post_analytics(
    post_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict[str, Any]:
    try:
        post = db.session.query(Post).filter_by(id=post_id).one_or_none()
        if not post:
            raise ValueError(f"Post with id {post_id} not found")

        if not start_date:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(UTC)

        total_views = (
            db.session.query(func.count(PageView.id))
            .filter(
                PageView.post_id == post_id,
                PageView.viewed_at >= start_date,
                PageView.viewed_at <= end_date,
            )
            .scalar()
        ) or 0

        unique_visitors = (
            db.session.query(func.count(func.distinct(PageView.visitor_id)))
            .filter(
                PageView.post_id == post_id,
                PageView.viewed_at >= start_date,
                PageView.viewed_at <= end_date,
            )
            .scalar()
        ) or 0

        avg_time = (
            db.session.query(func.avg(PageView.time_on_page))
            .filter(
                PageView.post_id == post_id,
                PageView.viewed_at >= start_date,
                PageView.viewed_at <= end_date,
                PageView.time_on_page.isnot(None),
            )
            .scalar()
        )

        ref_rows = (
            db.session.query(PageView.referrer, func.count(PageView.id).label("count"))
            .filter(
                PageView.post_id == post_id,
                PageView.viewed_at >= start_date,
                PageView.viewed_at <= end_date,
                PageView.referrer.isnot(None),
                PageView.referrer != "",
            )
            .group_by(PageView.referrer)
            .order_by(func.count(PageView.id).desc())
            .limit(10)
            .all()
        )
        referrers = [(str(r[0]), int(r[1])) for r in ref_rows]

        daily_rows = (
            db.session.query(
                func.date(PageView.viewed_at).label("date"),
                func.count(PageView.id).label("count"),
            )
            .filter(
                PageView.post_id == post_id,
                PageView.viewed_at >= start_date,
                PageView.viewed_at <= end_date,
            )
            .group_by(func.date(PageView.viewed_at))
            .order_by(func.date(PageView.viewed_at))
            .all()
        )
        daily_views = [[_iso_date(r[0]), int(r[1])] for r in daily_rows]

        return {
            "total_views": int(total_views),
            "unique_visitors": int(unique_visitors),
            "avg_time_on_page": float(avg_time) if avg_time is not None else None,
            "referrers": referrers,
            "daily_views": daily_views,
        }

    except ValueError:
        raise
    except Exception as e:
        current_app.logger.error(f"Error in get_post_analytics for post {post_id}: {e}")
        return {
            "total_views": 0,
            "unique_visitors": 0,
            "avg_time_on_page": None,
            "referrers": [],
            "daily_views": [],
        }
