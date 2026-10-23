"""Test data builders: one place that knows what a valid trade looks like.

Tests override only the fields they care about, which keeps each test's
intent obvious: trade_payload(today, price=6000) says "valid trade, bad price".
"""

from __future__ import annotations

import datetime as dt


def trade_payload(business_date: dt.date, **overrides) -> dict:
    payload = {
        "side": "BUY",
        "hub": "HB_HOUSTON",
        "product": "ON_PEAK",
        "quantity_mw": 10,
        "price": 42.0,
        "delivery_date": (business_date + dt.timedelta(days=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


def book(api, business_date: dt.date, **overrides) -> dict:
    """Book a trade through the API and return it. Fails loudly if rejected."""
    resp = api.post("/api/trades", data=trade_payload(business_date, **overrides))
    assert resp.status == 201, f"setup trade rejected: {resp.status} {resp.text()}"
    return resp.json()
