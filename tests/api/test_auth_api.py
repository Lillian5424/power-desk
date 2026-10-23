"""API-level access control. Faster and more thorough than doing this through the UI."""

from __future__ import annotations

import pytest

from tests.support.data import trade_payload

pytestmark = pytest.mark.smoke


def test_health_is_public(anon_api):
    resp = anon_api.get("/api/health")
    assert resp.ok
    assert resp.json()["status"] == "ok"


@pytest.mark.parametrize("path", ["/api/prices", "/api/trades", "/api/positions"])
def test_protected_endpoints_require_login(anon_api, path):
    assert anon_api.get(path).status == 401


def test_bad_password_is_rejected(anon_api):
    resp = anon_api.post("/api/login", data={"username": "trader1", "password": "wrong"})
    assert resp.status == 401


def test_login_returns_role(anon_api):
    resp = anon_api.post("/api/login", data={"username": "viewer1", "password": "viewer1pass"})
    assert resp.ok
    assert resp.json()["role"] == "viewer"


def test_session_cookie_grants_access(trader_api):
    assert trader_api.get("/api/prices").ok


def test_viewer_cannot_book_trades(viewer_api, business_date):
    resp = viewer_api.post("/api/trades", data=trade_payload(business_date))
    assert resp.status == 403


def test_logout_ends_session(trader_api):
    assert trader_api.post("/api/logout").ok
    assert trader_api.get("/api/trades").status == 401
