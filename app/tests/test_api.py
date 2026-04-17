"""Tests for the analytics tracking API."""

import json
import pytest


class TestTrackPageview:
    def test_missing_json_returns_error(self, client):
        # Analytics disabled in test config -> 403
        resp = client.post("/api/track/pageview", content_type="application/json")
        assert resp.status_code in (400, 403)

    def test_missing_required_fields(self, client, app):
        # Enable analytics for this test
        app.config["ANALYTICS_ENABLED"] = True
        resp = client.post(
            "/api/track/pageview",
            data=json.dumps({"path": "/test"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        app.config["ANALYTICS_ENABLED"] = False

    def test_invalid_visitor_id(self, client, app):
        app.config["ANALYTICS_ENABLED"] = True
        resp = client.post(
            "/api/track/pageview",
            data=json.dumps({
                "path": "/test",
                "session_id": "s" * 64,
                "visitor_id": "short",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Invalid visitor_id" in data["error"]
        app.config["ANALYTICS_ENABLED"] = False


class TestTrackHeartbeat:
    def test_missing_json_returns_error(self, client):
        resp = client.post("/api/track/heartbeat", content_type="application/json")
        assert resp.status_code in (400, 403)

    def test_missing_fields_returns_error(self, client, app):
        app.config["ANALYTICS_ENABLED"] = True
        resp = client.post(
            "/api/track/heartbeat",
            data=json.dumps({"pageview_id": 1}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        app.config["ANALYTICS_ENABLED"] = False

    def test_nonexistent_pageview_returns_404(self, client, app):
        app.config["ANALYTICS_ENABLED"] = True
        resp = client.post(
            "/api/track/heartbeat",
            data=json.dumps({"pageview_id": 99999, "time_spent": 10}),
            content_type="application/json",
        )
        assert resp.status_code == 404
        app.config["ANALYTICS_ENABLED"] = False


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
