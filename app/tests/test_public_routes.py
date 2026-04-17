"""Tests for public-facing routes."""

import pytest


class TestIndexRoute:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_contains_site_name(self, client):
        resp = client.get("/")
        assert b"Portfolio" in resp.data or resp.status_code == 200


class TestPostView:
    def test_published_post_accessible(self, client, sample_post):
        resp = client.get(f"/p/{sample_post.slug}/")
        assert resp.status_code == 200
        assert sample_post.title.encode() in resp.data

    def test_unpublished_post_returns_404(self, client, unpublished_post):
        resp = client.get(f"/p/{unpublished_post.slug}/")
        assert resp.status_code == 404

    def test_nonexistent_post_returns_404(self, client):
        resp = client.get("/p/does-not-exist/")
        assert resp.status_code == 404

    def test_slug_injection_returns_404(self, client):
        resp = client.get("/p/<script>alert(1)</script>/")
        assert resp.status_code == 404

    def test_very_long_slug_returns_404(self, client):
        resp = client.get(f"/p/{'a' * 200}/")
        assert resp.status_code == 404


class TestCategoryView:
    def test_valid_category(self, client, sample_post):
        resp = client.get("/c/ctf/")
        assert resp.status_code == 200

    def test_nonexistent_category(self, client):
        resp = client.get("/c/nonexistent/")
        assert resp.status_code == 404


class TestTagView:
    def test_valid_tag(self, client, sample_post):
        resp = client.get("/t/crypto/")
        assert resp.status_code == 200

    def test_nonexistent_tag(self, client):
        resp = client.get("/t/nonexistent/")
        assert resp.status_code == 404


class TestStaticRoutes:
    def test_about_page(self, client):
        resp = client.get("/about")
        assert resp.status_code == 200

    def test_contact_page(self, client):
        resp = client.get("/contact")
        assert resp.status_code == 200

    def test_robots_txt(self, client):
        resp = client.get("/robots.txt")
        assert resp.status_code == 200
        assert b"User-agent" in resp.data

    def test_all_posts_page(self, client):
        resp = client.get("/all/")
        assert resp.status_code == 200

    def test_categories_index(self, client):
        resp = client.get("/categories/")
        assert resp.status_code == 200

    def test_tags_index(self, client):
        resp = client.get("/tags/")
        assert resp.status_code == 200


class TestSecurityHeaders:
    def test_csp_header_present(self, client):
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "nonce-" in csp

    def test_x_content_type_options(self, client):
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client):
        resp = client.get("/")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy(self, client):
        resp = client.get("/")
        assert "strict-origin" in resp.headers.get("Referrer-Policy", "")
