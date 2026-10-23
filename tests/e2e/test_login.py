from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.pages import DashboardPage, LoginPage


@pytest.mark.smoke
def test_trader_can_sign_in_and_out(page: Page):
    login = LoginPage(page).open()
    login.login("trader1", "trader1pass")

    dashboard = DashboardPage(page)
    expect(page).to_have_url(re.compile(r"/$"))
    expect(dashboard.current_user).to_have_text("Alex Rivera")
    expect(dashboard.current_role).to_have_text("trader")

    dashboard.logout()
    expect(page).to_have_url(re.compile(r"/login$"))


def test_wrong_password_shows_error_and_keeps_username(page: Page):
    login = LoginPage(page).open()
    login.login("trader1", "not-the-password")

    expect(login.error).to_have_text("Invalid username or password.")
    expect(login.username).to_have_value("trader1")
    expect(login.password).to_have_value("")


def test_protected_page_redirects_to_login(page: Page):
    page.goto("/positions")
    expect(page).to_have_url(re.compile(r"/login$"))


def test_viewer_has_no_trade_ticket(login_as):
    page = login_as("viewer")
    dashboard = DashboardPage(page).open()

    expect(dashboard.current_role).to_have_text("viewer")
    expect(dashboard.nav_trade).to_have_count(0)

    # Hiding the link is not security: the page itself must refuse too.
    page.goto("/trades/new")
    expect(page.get_by_test_id("forbidden")).to_be_visible()
