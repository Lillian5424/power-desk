"""E2E fixtures.

Logging in through the UI is tested once (test_login.py). Every other test
logs in through the API instead, sharing the session cookie with the browser.
That is faster and means a broken login page fails one test, not fifty.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.conftest import USERS

expect.set_options(timeout=5_000)


@pytest.fixture(autouse=True)
def _clean_book(reset_data):
    """Every E2E test starts with an empty trade book."""


@pytest.fixture
def login_as(context, page: Page):
    """Factory: login_as("viewer") -> the `page` fixture, already signed in."""

    def _login(role: str) -> Page:
        username, password = USERS[role]
        # context.request shares cookies with the browser context
        resp = context.request.post("/api/login", data={"username": username, "password": password})
        assert resp.ok, f"API login as {role} failed: {resp.status}"
        return page

    return _login


@pytest.fixture
def trader_page(login_as) -> Page:
    return login_as("trader")


@pytest.fixture
def ui_api(context):
    """API client sharing the browser's session: seed data, then check it in the UI."""
    return context.request
