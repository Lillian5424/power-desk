"""The trade ticket: the most business-critical screen in the app."""

from __future__ import annotations

import datetime as dt
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.pages import BlotterPage, TradeTicketPage
from tests.support.data import book


@pytest.mark.smoke
def test_book_trade_happy_path(trader_page, business_date):
    delivery = (business_date + dt.timedelta(days=2)).isoformat()
    ticket = TradeTicketPage(trader_page).open()

    ticket.book(
        side="SELL", hub="HB_NORTH", product="OFF_PEAK", quantity_mw=20, price=37.5, delivery_date=delivery
    )

    blotter = BlotterPage(trader_page)
    expect(trader_page).to_have_url(re.compile(r"/blotter$"))
    expect(blotter.flash).to_contain_text("Trade #1 booked: SELL 20 MW HB_NORTH OFF_PEAK @ $37.50")
    expect(blotter.rows).to_have_count(1)
    expect(blotter.cell(1, "side")).to_have_text("SELL")
    expect(blotter.cell(1, "delivery_date")).to_have_text(delivery)
    expect(blotter.cell(1, "notional")).to_have_text("$6,000.00")  # 20 MW x 8 h x $37.50


def test_live_mark_and_notional_update_as_you_type(trader_page):
    ticket = TradeTicketPage(trader_page).open()
    expect(ticket.hub_mark).to_have_text("$42.50")  # HB_HOUSTON default

    ticket.hub.select_option("HB_WEST")
    expect(ticket.hub_mark).to_have_text("$31.20")

    ticket.fill(hub="HB_WEST", product="ATC", quantity_mw=5, price=30)
    expect(ticket.notional).to_have_text("$3,600.00")  # 5 MW x 24 h x $30


def test_validation_errors_are_shown_and_input_is_kept(trader_page):
    ticket = TradeTicketPage(trader_page).open()

    ticket.book(quantity_mw=150, price=6000)

    expect(ticket.error_with_code("QUANTITY_OUT_OF_RANGE")).to_be_visible()
    expect(ticket.error_with_code("PRICE_OUT_OF_RANGE")).to_be_visible()
    expect(ticket.quantity).to_have_value("150")
    expect(ticket.price).to_have_value("6000")


def test_off_market_price_requires_confirmation(trader_page):
    ticket = TradeTicketPage(trader_page).open()
    expect(ticket.confirm_price).to_have_count(0)  # no checkbox until it is needed

    ticket.book(price=95)  # >50% above the $42.50 mark
    expect(ticket.error_with_code("PRICE_CONFIRMATION_REQUIRED")).to_be_visible()

    ticket.confirm_price.check()
    ticket.submit.click()

    expect(BlotterPage(trader_page).flash).to_contain_text("booked")


def test_position_limit_message(trader_page, ui_api, business_date):
    # Seed through the API: fast, and not what this test is about
    book(ui_api, business_date, quantity_mw=100)
    book(ui_api, business_date, quantity_mw=100)

    ticket = TradeTicketPage(trader_page).open()
    ticket.book(quantity_mw=5)

    expect(ticket.error_with_code("POSITION_LIMIT_EXCEEDED")).to_contain_text("limit ±200 MW")
