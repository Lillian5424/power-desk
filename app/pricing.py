"""Settlement-point price marks ($/MWh) for each trading hub.

A real desk would pull these from a market-data feed. Here they are
deterministic per day so the app behaves the same every time you run it,
and completely fixed in the test environment so tests can assert exact P&L.
"""

from __future__ import annotations

import datetime as dt
import hashlib

BASE_MARKS = {
    "HB_HOUSTON": 42.50,
    "HB_NORTH": 38.75,
    "HB_SOUTH": 40.10,
    "HB_WEST": 31.20,
}


def get_marks(day: dt.date, *, fixed: bool = False) -> dict[str, float]:
    if fixed:
        return dict(BASE_MARKS)
    marks = {}
    for hub, base in BASE_MARKS.items():
        digest = hashlib.sha256(f"{hub}:{day.isoformat()}".encode()).hexdigest()
        jitter = int(digest[:8], 16) / 0xFFFFFFFF  # 0..1, stable for a given hub and day
        marks[hub] = round(base * (0.85 + 0.30 * jitter), 2)
    return marks
