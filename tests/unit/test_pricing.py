from __future__ import annotations

import datetime as dt

from app import pricing


def test_fixed_marks_equal_base_marks():
    assert pricing.get_marks(dt.date(2026, 11, 2), fixed=True) == pricing.BASE_MARKS


def test_marks_are_deterministic_per_day():
    day = dt.date(2026, 11, 2)
    assert pricing.get_marks(day) == pricing.get_marks(day)


def test_marks_stay_within_plus_minus_15_percent_of_base():
    for offset in range(60):
        marks = pricing.get_marks(dt.date(2026, 1, 1) + dt.timedelta(days=offset))
        for hub, base in pricing.BASE_MARKS.items():
            assert 0.85 * base - 0.01 <= marks[hub] <= 1.15 * base + 0.01
