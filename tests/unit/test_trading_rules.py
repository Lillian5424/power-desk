"""Unit tests for trading rules: no server, no browser, run in milliseconds.

Boundary values are where bugs live, so most rules are tested just inside
and just outside each limit.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app import trading
from app.trading import TradeRequest

TODAY = dt.date(2026, 11, 2)
MARK = 42.50


def make_req(**overrides) -> TradeRequest:
    fields = {
        "side": "BUY",
        "hub": "HB_HOUSTON",
        "product": "ON_PEAK",
        "quantity_mw": 10,
        "price": 42.0,
        "delivery_date": TODAY + dt.timedelta(days=1),
    }
    fields.update(overrides)
    return TradeRequest(**fields)


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def validate(req, current_net_mw=0, confirmed=False):
    return trading.validate_trade(
        req, today=TODAY, mark=MARK, current_net_mw=current_net_mw, price_confirmed=confirmed
    )


# ---------------------------------------------------------------- parsing


def test_parse_accepts_form_style_strings():
    req, issues = trading.parse_trade(
        {
            "side": "sell",
            "hub": "hb_west",
            "product": "atc",
            "quantity_mw": "25",
            "price": "31.5",
            "delivery_date": "2026-11-05",
        }
    )
    assert issues == []
    assert req == TradeRequest("SELL", "HB_WEST", "ATC", 25, 31.5, dt.date(2026, 11, 5))


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("side", "HOLD", "INVALID_SIDE"),
        ("hub", "HB_PAN", "INVALID_HUB"),
        ("product", "WEEKEND", "INVALID_PRODUCT"),
        ("quantity_mw", "10.5", "INVALID_QUANTITY"),
        ("quantity_mw", "ten", "INVALID_QUANTITY"),
        ("price", "", "INVALID_PRICE"),
        ("delivery_date", "11/03/2026", "INVALID_DATE"),
    ],
)
def test_parse_rejects_malformed_fields(field, value, code):
    data = {
        "side": "BUY",
        "hub": "HB_HOUSTON",
        "product": "ON_PEAK",
        "quantity_mw": "10",
        "price": "42",
        "delivery_date": "2026-11-03",
        field: value,
    }
    req, issues = trading.parse_trade(data)
    assert req is None
    assert codes(issues) == {code}


def test_parse_reports_every_bad_field_at_once():
    _, issues = trading.parse_trade({})
    assert len(issues) == 6


# ---------------------------------------------------------------- validation


def test_valid_trade_has_no_issues():
    assert validate(make_req()) == []


@pytest.mark.parametrize(
    ("qty", "ok"),
    [(0, False), (1, True), (100, True), (101, False), (-5, False)],
)
def test_quantity_limits(qty, ok):
    assert ("QUANTITY_OUT_OF_RANGE" not in codes(validate(make_req(quantity_mw=qty)))) is ok


@pytest.mark.parametrize(
    ("price", "ok"),
    [(-250.0, True), (-250.01, False), (5000.0, True), (5000.01, False)],
)
def test_price_floor_and_cap(price, ok):
    issues = validate(make_req(price=price), confirmed=True)
    assert ("PRICE_OUT_OF_RANGE" not in codes(issues)) is ok


@pytest.mark.parametrize(
    ("days_ahead", "code"),
    [
        (-1, "DELIVERY_NOT_FUTURE"),
        (0, "DELIVERY_NOT_FUTURE"),
        (1, None),
        (30, None),
        (31, "DELIVERY_TOO_FAR"),
    ],
)
def test_delivery_window(days_ahead, code):
    issues = validate(make_req(delivery_date=TODAY + dt.timedelta(days=days_ahead)))
    assert codes(issues) == ({code} if code else set())


class TestPositionLimit:
    def test_trade_up_to_limit_is_allowed(self):
        assert validate(make_req(quantity_mw=100), current_net_mw=100) == []

    def test_trade_beyond_limit_is_rejected(self):
        issues = validate(make_req(quantity_mw=1), current_net_mw=200)
        assert codes(issues) == {"POSITION_LIMIT_EXCEEDED"}

    def test_short_side_limit_applies_too(self):
        issues = validate(make_req(side="SELL", quantity_mw=50), current_net_mw=-180)
        assert codes(issues) == {"POSITION_LIMIT_EXCEEDED"}

    def test_risk_reducing_trade_allowed_even_when_over_limit(self):
        # e.g. limit was lowered overnight; trader must still be able to cut risk.
        assert validate(make_req(side="SELL", quantity_mw=20), current_net_mw=250) == []


class TestFatFingerCheck:
    def test_price_near_mark_needs_no_confirmation(self):
        assert validate(make_req(price=MARK * 1.5)) == []

    def test_price_far_from_mark_needs_confirmation(self):
        issues = validate(make_req(price=MARK * 1.51))
        assert codes(issues) == {"PRICE_CONFIRMATION_REQUIRED"}

    def test_confirmed_off_market_price_is_accepted(self):
        assert validate(make_req(price=MARK * 3), confirmed=True) == []

    def test_no_mark_means_no_check(self):
        issues = trading.validate_trade(make_req(price=999), today=TODAY, mark=None, current_net_mw=0)
        assert issues == []


# ---------------------------------------------------------------- economics


def test_trade_mwh_and_notional():
    req = make_req(quantity_mw=25, product="OFF_PEAK", price=30.0)
    assert req.mwh == 200
    assert req.notional == 6000.0


def _trade(side, hub, product, qty, price):
    return {"side": side, "hub": hub, "product": product, "quantity_mw": qty, "price": price}


def test_positions_single_long_trade():
    result = trading.compute_positions(
        [_trade("BUY", "HB_HOUSTON", "ON_PEAK", 10, 40.0)], {"HB_HOUSTON": 42.5}
    )
    # 10 MW * 16 h = 160 MWh long; mark is $2.50 above entry -> +$400
    assert result["rows"] == [
        {"hub": "HB_HOUSTON", "net_mw": 10, "net_mwh": 160, "avg_price": 40.0, "mark": 42.5, "pnl": 400.0}
    ]
    assert result["total_pnl"] == 400.0


def test_positions_short_loses_when_price_rises():
    result = trading.compute_positions([_trade("SELL", "HB_WEST", "ATC", 5, 30.0)], {"HB_WEST": 31.2})
    assert result["rows"][0]["net_mwh"] == -120
    assert result["total_pnl"] == pytest.approx(-144.0)


def test_flat_position_keeps_realized_pnl_and_has_no_avg_price():
    trades = [
        _trade("BUY", "HB_NORTH", "ON_PEAK", 10, 35.0),
        _trade("SELL", "HB_NORTH", "ON_PEAK", 10, 38.0),
    ]
    row = trading.compute_positions(trades, {"HB_NORTH": 38.75})["rows"][0]
    assert row["net_mw"] == 0
    assert row["avg_price"] is None
    assert row["pnl"] == pytest.approx(160 * 3.0)  # bought 35, sold 38


def test_positions_sum_across_hubs():
    trades = [
        _trade("BUY", "HB_HOUSTON", "ON_PEAK", 10, 40.0),
        _trade("SELL", "HB_WEST", "ATC", 5, 30.0),
    ]
    result = trading.compute_positions(trades, {"HB_HOUSTON": 42.5, "HB_WEST": 31.2})
    assert [r["hub"] for r in result["rows"]] == ["HB_HOUSTON", "HB_WEST"]
    assert result["total_pnl"] == pytest.approx(400.0 - 144.0)
