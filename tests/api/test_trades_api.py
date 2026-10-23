"""Trade booking through the JSON API.

The unit tests prove each rule in isolation; these prove the rules are
actually wired into the endpoint, with the right status codes and payloads.
"""

from __future__ import annotations

import datetime as dt

import pytest

from tests.support.data import book, trade_payload


@pytest.mark.smoke
def test_book_trade_returns_201_and_enriched_trade(trader_api, business_date):
    resp = trader_api.post("/api/trades", data=trade_payload(business_date, quantity_mw=25, price=40.0))

    assert resp.status == 201
    trade = resp.json()
    assert trade["id"] > 0
    assert trade["trader"] == "trader1"
    assert trade["mwh"] == 25 * 16
    assert trade["notional"] == 25 * 16 * 40.0


def test_booked_trade_appears_in_list(trader_api, business_date):
    trade = book(trader_api, business_date)
    ids = [t["id"] for t in trader_api.get("/api/trades").json()["trades"]]
    assert trade["id"] in ids


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"quantity_mw": 0}, "QUANTITY_OUT_OF_RANGE"),
        ({"quantity_mw": 150}, "QUANTITY_OUT_OF_RANGE"),
        ({"price": 6000}, "PRICE_OUT_OF_RANGE"),
        ({"price": 400}, "PRICE_CONFIRMATION_REQUIRED"),
        ({"hub": "HB_PAN"}, "INVALID_HUB"),
        ({"side": "HOLD"}, "INVALID_SIDE"),
    ],
)
def test_invalid_trades_are_rejected_with_error_codes(trader_api, business_date, overrides, expected_code):
    resp = trader_api.post("/api/trades", data=trade_payload(business_date, **overrides))

    assert resp.status == 422
    assert expected_code in [e["code"] for e in resp.json()["errors"]]


def test_delivery_today_is_rejected(trader_api, business_date):
    resp = trader_api.post(
        "/api/trades", data=trade_payload(business_date, delivery_date=business_date.isoformat())
    )
    assert resp.status == 422
    assert resp.json()["errors"][0]["code"] == "DELIVERY_NOT_FUTURE"


def test_off_market_price_books_when_confirmed(trader_api, business_date):
    resp = trader_api.post("/api/trades", data=trade_payload(business_date, price=400, confirm_price=True))
    assert resp.status == 201


def test_position_limit_accumulates_across_trades(trader_api, business_date):
    book(trader_api, business_date, quantity_mw=100)
    book(trader_api, business_date, quantity_mw=100)  # now at +200 MW, the limit

    resp = trader_api.post("/api/trades", data=trade_payload(business_date, quantity_mw=1))
    assert resp.status == 422
    assert resp.json()["errors"][0]["code"] == "POSITION_LIMIT_EXCEEDED"

    # ...but selling to reduce risk is still allowed
    assert trader_api.post("/api/trades", data=trade_payload(business_date, side="SELL")).status == 201


def test_position_limit_is_per_trader(api_as, business_date):
    trader1, trader2 = api_as("trader"), api_as("trader2")
    book(trader1, business_date, quantity_mw=100)
    book(trader1, business_date, quantity_mw=100)

    # trader1 is at the limit; trader2 has their own, independent limit
    assert trader2.post("/api/trades", data=trade_payload(business_date, quantity_mw=50)).status == 201


def test_traders_only_see_their_own_trades_and_viewer_sees_all(api_as, business_date):
    trader1, trader2, viewer = api_as("trader"), api_as("trader2"), api_as("viewer")
    book(trader1, business_date)
    book(trader2, business_date)

    assert {t["trader"] for t in trader1.get("/api/trades").json()["trades"]} == {"trader1"}
    assert {t["trader"] for t in viewer.get("/api/trades").json()["trades"]} == {"trader1", "trader2"}


def test_hub_filter(trader_api, business_date):
    book(trader_api, business_date, hub="HB_NORTH", price=38.0)
    book(trader_api, business_date, hub="HB_WEST", price=31.0)

    trades = trader_api.get("/api/trades", params={"hub": "HB_WEST"}).json()["trades"]
    assert [t["hub"] for t in trades] == ["HB_WEST"]


def test_far_dated_delivery_rejected(trader_api, business_date):
    far = (business_date + dt.timedelta(days=31)).isoformat()
    resp = trader_api.post("/api/trades", data=trade_payload(business_date, delivery_date=far))
    assert resp.json()["errors"][0]["code"] == "DELIVERY_TOO_FAR"
