"""Trading rules: parsing, validation and position / P&L math.

Pure functions with no I/O, so they can be unit-tested in milliseconds.
Both the HTML trade ticket and the JSON API go through `parse_trade` and
`validate_trade`, so every rule has exactly one implementation.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

SIDES = ("BUY", "SELL")
HUBS = ("HB_HOUSTON", "HB_NORTH", "HB_SOUTH", "HB_WEST")
# Hours of delivery per day for each block product.
PRODUCT_HOURS = {"ON_PEAK": 16, "OFF_PEAK": 8, "ATC": 24}

MIN_TRADE_MW = 1
MAX_TRADE_MW = 100
PRICE_FLOOR = -250.0  # $/MWh
PRICE_CAP = 5000.0  # $/MWh
MAX_DAYS_FORWARD = 30
POSITION_LIMIT_MW = 200  # max absolute net MW per trader per hub
FAT_FINGER_PCT = 0.50  # price this far from the mark needs explicit confirmation


@dataclass(frozen=True)
class TradeRequest:
    side: str
    hub: str
    product: str
    quantity_mw: int
    price: float
    delivery_date: dt.date

    @property
    def signed_mw(self) -> int:
        return self.quantity_mw if self.side == "BUY" else -self.quantity_mw

    @property
    def mwh(self) -> int:
        return self.quantity_mw * PRODUCT_HOURS[self.product]

    @property
    def notional(self) -> float:
        return round(self.mwh * self.price, 2)


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "field": self.field, "message": self.message}


def parse_trade(data: Mapping) -> tuple[TradeRequest | None, list[Issue]]:
    """Turn raw input (form fields or JSON) into a typed TradeRequest."""
    issues: list[Issue] = []

    side = str(data.get("side", "")).strip().upper()
    if side not in SIDES:
        issues.append(Issue("INVALID_SIDE", "side", "Side must be BUY or SELL."))

    hub = str(data.get("hub", "")).strip().upper()
    if hub not in HUBS:
        issues.append(Issue("INVALID_HUB", "hub", f"Hub must be one of {', '.join(HUBS)}."))

    product = str(data.get("product", "")).strip().upper()
    if product not in PRODUCT_HOURS:
        issues.append(Issue("INVALID_PRODUCT", "product", "Product must be ON_PEAK, OFF_PEAK or ATC."))

    quantity = None
    raw_qty = data.get("quantity_mw", "")
    try:
        as_float = float(str(raw_qty).strip())
        if not as_float.is_integer():
            raise ValueError
        quantity = int(as_float)
    except ValueError:
        issues.append(Issue("INVALID_QUANTITY", "quantity_mw", "Quantity must be a whole number of MW."))

    price = None
    try:
        price = float(str(data.get("price", "")).strip())
    except ValueError:
        issues.append(Issue("INVALID_PRICE", "price", "Price must be a number."))

    delivery = None
    try:
        delivery = dt.date.fromisoformat(str(data.get("delivery_date", "")).strip())
    except ValueError:
        issues.append(Issue("INVALID_DATE", "delivery_date", "Delivery date must be YYYY-MM-DD."))

    if issues:
        return None, issues
    return TradeRequest(side, hub, product, quantity, price, delivery), []


def validate_trade(
    req: TradeRequest,
    *,
    today: dt.date,
    mark: float | None,
    current_net_mw: int,
    price_confirmed: bool = False,
) -> list[Issue]:
    """Business rules a well-formed trade must still pass before booking."""
    issues: list[Issue] = []

    if not MIN_TRADE_MW <= req.quantity_mw <= MAX_TRADE_MW:
        issues.append(
            Issue(
                "QUANTITY_OUT_OF_RANGE",
                "quantity_mw",
                f"Quantity must be between {MIN_TRADE_MW} and {MAX_TRADE_MW} MW.",
            )
        )

    price_in_range = PRICE_FLOOR <= req.price <= PRICE_CAP
    if not price_in_range:
        issues.append(
            Issue(
                "PRICE_OUT_OF_RANGE",
                "price",
                f"Price must be between ${PRICE_FLOOR:,.0f} and ${PRICE_CAP:,.0f}/MWh.",
            )
        )

    if req.delivery_date <= today:
        issues.append(Issue("DELIVERY_NOT_FUTURE", "delivery_date", "Delivery must be after today."))
    elif req.delivery_date > today + dt.timedelta(days=MAX_DAYS_FORWARD):
        issues.append(
            Issue(
                "DELIVERY_TOO_FAR",
                "delivery_date",
                f"Delivery must be within {MAX_DAYS_FORWARD} days.",
            )
        )

    # Risk-reducing trades are always allowed, even when the trader is over the limit.
    new_net = current_net_mw + req.signed_mw
    if abs(new_net) > POSITION_LIMIT_MW and abs(new_net) > abs(current_net_mw):
        issues.append(
            Issue(
                "POSITION_LIMIT_EXCEEDED",
                "quantity_mw",
                f"Trade would take net {req.hub} position to {new_net} MW (limit ±{POSITION_LIMIT_MW} MW).",
            )
        )

    if price_in_range and mark and not price_confirmed:
        deviation = abs(req.price - mark) / abs(mark)
        if deviation > FAT_FINGER_PCT:
            issues.append(
                Issue(
                    "PRICE_CONFIRMATION_REQUIRED",
                    "price",
                    f"Price ${req.price:,.2f} is {deviation:.0%} away from the "
                    f"${mark:,.2f} mark. Confirm to book anyway.",
                )
            )

    return issues


def compute_positions(trades: Iterable[Mapping], marks: Mapping[str, float]) -> dict:
    """Aggregate trades into net positions and mark-to-market P&L per hub.

    P&L for one trade = signed MWh * (mark - trade price).
    """
    by_hub: dict[str, dict] = {}
    for t in trades:
        hours = PRODUCT_HOURS[t["product"]]
        signed_mw = t["quantity_mw"] if t["side"] == "BUY" else -t["quantity_mw"]
        signed_mwh = signed_mw * hours
        row = by_hub.setdefault(t["hub"], {"net_mw": 0, "net_mwh": 0, "cost": 0.0, "pnl": 0.0})
        row["net_mw"] += signed_mw
        row["net_mwh"] += signed_mwh
        row["cost"] += signed_mwh * t["price"]
        row["pnl"] += signed_mwh * (marks[t["hub"]] - t["price"])

    rows = []
    for hub in sorted(by_hub):
        r = by_hub[hub]
        rows.append(
            {
                "hub": hub,
                "net_mw": r["net_mw"],
                "net_mwh": r["net_mwh"],
                "avg_price": round(r["cost"] / r["net_mwh"], 2) if r["net_mwh"] else None,
                "mark": marks[hub],
                "pnl": round(r["pnl"], 2),
            }
        )
    return {"rows": rows, "total_pnl": round(sum(r["pnl"] for r in rows), 2)}
