"""Metric helpers: division by zero, rounding, currency formatting, and timezone windows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.analytics.metrics import local_window_to_utc, money_str, rate_float, safe_rate


def test_safe_rate_returns_none_on_zero_denominator() -> None:
    assert safe_rate(0, 0) is None
    assert safe_rate(5, 0) is None


def test_safe_rate_quantises_to_four_places() -> None:
    assert safe_rate(2, 6) == Decimal("0.3333")
    assert safe_rate(1, 4) == Decimal("0.2500")
    assert safe_rate(0, 10) == Decimal("0.0000")


def test_rate_float_passes_none_through() -> None:
    assert rate_float(None) is None
    assert rate_float(Decimal("0.5")) == 0.5


def test_money_str_is_fixed_point_and_never_float() -> None:
    assert money_str(Decimal("135.5")) == "135.50"
    assert money_str(None) == "0.00"
    assert money_str(7) == "7.00"


def test_local_window_uses_merchant_timezone_not_utc() -> None:
    # 2026-03-01 in Los Angeles (UTC-08:00) runs from 08:00Z to 08:00Z the next day.
    start, end = local_window_to_utc("America/Los_Angeles", date(2026, 3, 1), date(2026, 3, 1))
    assert start == datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    assert end == datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


def test_local_window_is_half_open_and_includes_last_local_day() -> None:
    start, end = local_window_to_utc("America/Los_Angeles", date(2026, 3, 1), date(2026, 3, 4))
    assert start == datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    # The end bound is the start of the day AFTER the last included local date, so 2026-03-05
    # 00:00 local is excluded and 2026-03-04 23:59:59 local is included.
    assert end == datetime(2026, 3, 5, 8, 0, tzinfo=UTC)


def test_dst_spring_forward_day_is_23_hours_long() -> None:
    # 2026-03-08 is the US spring-forward date in America/Los_Angeles.
    start, end = local_window_to_utc("America/Los_Angeles", date(2026, 3, 8), date(2026, 3, 8))
    assert (end - start).total_seconds() == 23 * 3600


def test_local_window_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        local_window_to_utc("UTC", date(2026, 3, 5), date(2026, 3, 1))
