from __future__ import annotations

from playwright.sync_api import Locator, Page

from .base_page import BasePage


class PositionsPage(BasePage):
    path = "/positions"

    def __init__(self, page: Page):
        super().__init__(page)
        self.total_pnl = page.get_by_test_id("positions-total-pnl")
        self.empty = page.get_by_test_id("positions-empty")

    def cell(self, hub: str, column: str) -> Locator:
        return self.page.get_by_test_id(f"position-{hub}").locator(f'[data-col="{column}"]')
