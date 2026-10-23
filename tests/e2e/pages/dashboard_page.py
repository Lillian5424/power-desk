from __future__ import annotations

from playwright.sync_api import Locator, Page

from .base_page import BasePage


class DashboardPage(BasePage):
    path = "/"

    def __init__(self, page: Page):
        super().__init__(page)
        self.trade_count = page.get_by_test_id("trade-count")
        self.total_pnl = page.get_by_test_id("total-pnl")
        self.marks_table = page.get_by_test_id("marks-table")

    def mark_row(self, hub: str) -> Locator:
        return self.page.get_by_test_id(f"mark-{hub}")
