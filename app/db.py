"""SQLite persistence for booked trades."""

from __future__ import annotations

import datetime as dt
import os
import sqlite3
from contextlib import closing

from .trading import PRODUCT_HOURS, TradeRequest

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trader        TEXT    NOT NULL,
    side          TEXT    NOT NULL,
    hub           TEXT    NOT NULL,
    product       TEXT    NOT NULL,
    quantity_mw   INTEGER NOT NULL,
    price         REAL    NOT NULL,
    delivery_date TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(os.getenv("DB_PATH", "power_desk.db"))
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(SCHEMA)


def _to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["mwh"] = d["quantity_mw"] * PRODUCT_HOURS[d["product"]]
    d["notional"] = round(d["mwh"] * d["price"], 2)
    return d


def insert_trade(trader: str, req: TradeRequest) -> dict:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO trades (trader, side, hub, product, quantity_mw, price, delivery_date, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trader,
                req.side,
                req.hub,
                req.product,
                req.quantity_mw,
                req.price,
                req.delivery_date.isoformat(),
                now,
            ),
        )
        row = conn.execute("SELECT * FROM trades WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _to_dict(row)


def list_trades(trader: str | None = None, hub: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM trades WHERE 1=1", []
    if trader:
        sql += " AND trader = ?"
        params.append(trader)
    if hub:
        sql += " AND hub = ?"
        params.append(hub)
    sql += " ORDER BY id DESC"
    with closing(_connect()) as conn:
        return [_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def net_mw(trader: str, hub: str) -> int:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE side WHEN 'BUY' THEN quantity_mw ELSE -quantity_mw END), 0)"
            " FROM trades WHERE trader = ? AND hub = ?",
            (trader, hub),
        ).fetchone()
    return int(row[0])


def reset() -> None:
    with closing(_connect()) as conn, conn:
        conn.execute("DELETE FROM trades")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'trades'")
