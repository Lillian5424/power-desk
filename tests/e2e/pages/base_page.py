from __future__ import annotations

from playwright.sync_api import Page


class BasePage:
    """Things every logged-in page has: the top navigation bar and flash messages."""

    path = "/"

    def __init__(self, page: Page):
        self.page = page
        self.current_user = page.get_by_test_id("current-user")
        self.current_role = page.get_by_test_id("current-role")
        self.flash = page.get_by_test_id("flash")
        self.nav_trade = page.get_by_test_id("nav-trade")
        self.nav_blotter = page.get_by_test_id("nav-blotter")
        self.nav_positions = page.get_by_test_id("nav-positions")
        self.logout_link = page.get_by_test_id("logout")

    def open(self):
        self.page.goto(self.path)
        return self

    def logout(self) -> None:
        self.logout_link.click()
