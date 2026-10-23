"""Positions and P&L through the API.

These need the test environment's fixed marks (HB_HOUSTON = 42.50, HB_WEST = 31.20)
so the expected numbers can be computed by hand.
"""

from __future__ import annotations

import pytest

from tests.support.data import book


@pytest.mark.smoke
def test_long_position_pnl(trader_api, business_date):
    book(trader_api, business_date, hub="HB_HOUSTON", product="ON_PEAK", quantity_mw=10, price=40.0)

    result = trader_api.get("/api/positions").json()

    # 10 MW x 16 h = 160 MWh, marked $2.50 above entry
    assert result["rows"][0]["net_mwh"] == 160
    assert result["total_pnl"] == pytest.approx(400.0)


def test_positions_net_long_and_short_across_hubs(trader_api, business_date):
    book(trader_api, business_date, hub="HB_HOUSTON", quantity_mw=10, price=40.0)
    book(trader_api, business_date, hub="HB_WEST", product="ATC", side="SELL", quantity_mw=5, price=30.0)

    result = trader_api.get("/api/positions").json()

    by_hub = {r["hub"]: r for r in result["rows"]}
    assert by_hub["HB_WEST"]["net_mw"] == -5
    assert by_hub["HB_WEST"]["pnl"] == pytest.approx(-144.0)
    assert result["total_pnl"] == pytest.approx(256.0)


def test_empty_book_has_no_positions(trader_api):
    assert trader_api.get("/api/positions").json() == {"rows": [], "total_pnl": 0}
