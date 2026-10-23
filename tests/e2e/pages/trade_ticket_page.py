from __future__ import annotations

from playwright.sync_api import Locator, Page

from .base_page import BasePage


class TradeTicketPage(BasePage):
    path = "/trades/new"

    def __init__(self, page: Page):
        super().__init__(page)
        self.hub = page.get_by_label("Hub")
        self.product = page.get_by_label("Product")
        self.quantity = page.get_by_label("Quantity (MW)")
        self.price = page.get_by_label("Price ($/MWh)")
        self.delivery_date = page.get_by_label("Delivery date")
        self.confirm_price = page.get_by_test_id("confirm-price")
        self.submit = page.get_by_role("button", name="Book trade")
        self.errors = page.get_by_test_id("form-errors")
        self.hub_mark = page.get_by_test_id("hub-mark")
        self.notional = page.get_by_test_id("notional")

    def side(self, side: str) -> Locator:
        return self.page.get_by_role("radio", name=side.capitalize())

    def fill(
        self,
        *,
        side: str = "BUY",
        hub: str = "HB_HOUSTON",
        product: str = "ON_PEAK",
        quantity_mw: int | str = 10,
        price: float | str = 42.0,
        delivery_date: str | None = None,
    ) -> TradeTicketPage:
        self.side(side).check()
        self.hub.select_option(hub)
        self.product.select_option(product)
        self.quantity.fill(str(quantity_mw))
        self.price.fill(str(price))
        if delivery_date:
            self.delivery_date.fill(delivery_date)
        return self

    def book(self, **fields) -> None:
        self.fill(**fields)
        self.submit.click()

    def error_with_code(self, code: str) -> Locator:
        return self.errors.locator(f'[data-error-code="{code}"]')
