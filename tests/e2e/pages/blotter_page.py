from __future__ import annotations

from playwright.sync_api import Locator, Page

from .base_page import BasePage


class BlotterPage(BasePage):
    path = "/blotter"

    def __init__(self, page: Page):
        super().__init__(page)
        self.rows = page.get_by_test_id("trade-row")
        self.empty = page.get_by_test_id("blotter-empty")
        self.hub_filter = page.get_by_label("Filter by hub")

    def row(self, trade_id: int) -> Locator:
        return self.page.locator(f'[data-testid="trade-row"][data-trade-id="{trade_id}"]')

    def cell(self, trade_id: int, column: str) -> Locator:
        return self.row(trade_id).locator(f'[data-col="{column}"]')

    def column(self, column: str) -> Locator:
        return self.rows.locator(f'[data-col="{column}"]')

    def filter_by_hub(self, hub: str) -> None:
        self.hub_filter.select_option(hub)  # page reloads via form submit
