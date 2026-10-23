"""Blotter and positions: seed trades via the API, verify what the UI shows.

"Arrange through the API, assert through the UI" is the most useful E2E
pattern there is: tests stay fast and each one checks one screen.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.e2e.pages import BlotterPage, DashboardPage, PositionsPage
from tests.support.data import book


def test_empty_blotter(trader_page):
    blotter = BlotterPage(trader_page).open()
    expect(blotter.empty).to_be_visible()


def test_blotter_filters_by_hub(trader_page, ui_api, business_date):
    book(ui_api, business_date, hub="HB_NORTH", price=38.0)
    book(ui_api, business_date, hub="HB_WEST", price=31.0)
    book(ui_api, business_date, hub="HB_NORTH", price=39.0)

    blotter = BlotterPage(trader_page).open()
    expect(blotter.rows).to_have_count(3)

    blotter.filter_by_hub("HB_NORTH")
    expect(blotter.rows).to_have_count(2)
    expect(blotter.column("hub")).to_have_text(["HB_NORTH", "HB_NORTH"])


def test_blotter_newest_first(trader_page, ui_api, business_date):
    first = book(ui_api, business_date)
    second = book(ui_api, business_date)

    blotter = BlotterPage(trader_page).open()
    expect(blotter.column("id")).to_have_text([str(second["id"]), str(first["id"])])


@pytest.mark.smoke
def test_positions_page_shows_pnl(trader_page, ui_api, business_date):
    book(ui_api, business_date, hub="HB_HOUSTON", quantity_mw=10, price=40.0)
    book(ui_api, business_date, hub="HB_WEST", product="ATC", side="SELL", quantity_mw=5, price=30.0)

    positions = PositionsPage(trader_page).open()

    expect(positions.cell("HB_HOUSTON", "net_mw")).to_have_text("10")
    expect(positions.cell("HB_HOUSTON", "pnl")).to_have_text("$400.00")
    expect(positions.cell("HB_WEST", "net_mw")).to_have_text("-5")
    expect(positions.cell("HB_WEST", "pnl")).to_have_text("-$144.00")
    expect(positions.total_pnl).to_have_text("$256.00")


def test_dashboard_summary_matches_book(trader_page, ui_api, business_date):
    book(ui_api, business_date, quantity_mw=10, price=40.0)

    dashboard = DashboardPage(trader_page).open()

    expect(dashboard.trade_count).to_have_text("1")
    expect(dashboard.total_pnl).to_have_text("$400.00")
    expect(dashboard.mark_row("HB_HOUSTON")).to_contain_text("42.50")
