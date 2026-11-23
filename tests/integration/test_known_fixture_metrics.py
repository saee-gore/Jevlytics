"""Analytics metrics against the hand-computed known fixture (tests/fixtures/known_data.py)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsQuery, MerchantNotFoundError, run_analytics
from tests.fixtures import known_data as kd

pytestmark = pytest.mark.integration

A = kd.MERCHANT_A
B = kd.MERCHANT_B
WINDOW = AnalyticsQuery(start=date(2026, 3, 1), end=date(2026, 3, 4))
E = kd.EXPECTED


def _run(session: Session, tool: str, merchant: str = A, query: AnalyticsQuery = WINDOW) -> dict[str, Any]:
    return run_analytics(session, tool, merchant, query)


def test_volume_is_separated_by_currency_and_excludes_non_approved(ro_session: Session) -> None:
    result = _run(ro_session, "get_transaction_volume")
    got = {
        row["currency"]: (str(row["approved_count"]), row["approved_volume"]) for row in result["by_currency"]
    }
    assert got == E["volume_by_currency"]
    assert result["total_approved_count"] == 4


def test_transaction_counts_by_status(ro_session: Session) -> None:
    result = _run(ro_session, "get_transaction_count")
    assert {row["status"]: row["transaction_count"] for row in result["by_status"]} == E["status_counts"]


def test_decline_reasons_and_shares(ro_session: Session) -> None:
    result = _run(ro_session, "get_decline_reasons")
    assert {r["decline_reason"]: r["declined_count"] for r in result["reasons"]} == E["decline_reasons"]
    assert result["total_declined"] == 2
    assert all(r["share_of_declines"] == 0.5 for r in result["reasons"])


def test_decline_rate_overall_and_by_network(ro_session: Session) -> None:
    result = _run(ro_session, "get_decline_rate")
    assert result["decline_rate"] == pytest.approx(float(E["decline_rate_overall"]))
    by_network = {r["card_network"]: r["decline_rate"] for r in result["by_card_network"]}
    assert by_network == {k: pytest.approx(float(v)) for k, v in E["decline_rate_by_network"].items()}


def test_decline_rate_omits_network_breakdown_when_network_is_filtered(ro_session: Session) -> None:
    filtered = AnalyticsQuery(start=WINDOW.start, end=WINDOW.end, card_network="VISA")
    result = _run(ro_session, "get_decline_rate", query=filtered)
    assert "by_card_network" not in result
    assert result["transaction_count"] == 4  # VISA attempts: t1, t4, t5, t6
    assert result["decline_rate"] == pytest.approx(0.25)


def test_settlement_volume_uses_settlement_date_window(ro_session: Session) -> None:
    result = _run(ro_session, "get_settlement_volume")
    usd = next(r for r in result["by_currency"] if r["currency"] == "USD")
    assert (str(usd["settlement_count"]), usd["settled_volume"]) == E[
        "settled_usd"
    ]  # stl_a_2 is 03-05, excluded


def test_chargeback_rate_is_cohort_by_original_transaction(ro_session: Session) -> None:
    # The chargeback (2026-03-20) falls after the window, but its original transaction is inside it.
    result = _run(ro_session, "get_chargeback_rate")
    assert result["approved_transaction_count"] == 4
    assert result["chargeback_count"] == 1
    assert result["chargeback_rate"] == pytest.approx(float(E["chargeback_rate"]))


def test_card_type_performance_per_currency(ro_session: Session) -> None:
    result = _run(ro_session, "get_card_type_performance")
    buckets = {(b["card_type"], b["currency"]): b for b in result["by_card_type_and_currency"]}
    debit_usd = buckets[("DEBIT", "USD")]
    assert (debit_usd["approved_count"], debit_usd["declined_count"]) == (1, 2)
    assert debit_usd["decline_rate"] == pytest.approx(float(E["card_type_debit_usd"]["rate"]))
    assert debit_usd["approved_volume"] == E["card_type_debit_usd"]["volume"]
    credit_usd = buckets[("CREDIT", "USD")]
    assert (credit_usd["approved_count"], credit_usd["declined_count"]) == (2, 0)
    assert credit_usd["decline_rate"] == 0.0
    assert credit_usd["approved_volume"] == E["card_type_credit_usd"]["volume"]
    assert buckets[("DEBIT", "CAD")]["approved_volume"] == "200.00"


def test_volume_by_region_keeps_currencies_apart(ro_session: Session) -> None:
    result = _run(ro_session, "get_transaction_volume_by_region")
    rows = {
        (r["region"], r["currency"]): (str(r["approved_count"]), r["approved_volume"])
        for r in result["by_region_and_currency"]
    }
    assert rows[("R1", "USD")] == E["region_r1_usd"]
    assert rows[("R2", "USD")] == E["region_r2_usd"]
    assert rows[("R2", "CAD")] == E["region_r2_cad"]


def test_fraud_indicators_use_merchant_local_day(ro_session: Session) -> None:
    # t2 is 23:30 on 2026-03-01 in Los Angeles. In UTC that is 2026-03-02 07:30, so a UTC grouping
    # would put it on the wrong day.
    result = _run(ro_session, "get_fraud_indicators")
    assert result["flagged_count"] == E["fraud_flagged"]
    assert result["transaction_count"] == E["fraud_total"]
    assert result["by_day_and_reason"] == [
        {"local_day": "2026-03-01", "risk_reason": "VELOCITY_BREACH", "flagged_count": 1}
    ]
    assert "not confirmed fraud" in result["note"]


def test_single_local_day_boundary_excludes_next_local_day(ro_session: Session) -> None:
    one_day = AnalyticsQuery(start=date(2026, 3, 1), end=date(2026, 3, 1))
    result = _run(ro_session, "get_transaction_volume", query=one_day)
    usd = next(r for r in result["by_currency"] if r["currency"] == "USD")
    assert (usd["approved_count"], usd["approved_volume"]) == (
        1,
        "100.00",
    )  # t3 at 00:30 local 03-02 excluded
    declines = _run(ro_session, "get_decline_reasons", query=one_day)
    assert declines["total_declined"] == 1  # t2 at 23:30 local 03-01 included


def test_empty_period_returns_zeros_and_none_without_errors(ro_session: Session) -> None:
    empty = AnalyticsQuery(start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert _run(ro_session, "get_transaction_volume", query=empty)["by_currency"] == []
    assert _run(ro_session, "get_decline_rate", query=empty)["decline_rate"] is None
    assert _run(ro_session, "get_chargeback_rate", query=empty)["chargeback_rate"] is None
    fraud = _run(ro_session, "get_fraud_indicators", query=empty)
    assert fraud["flagged_rate"] is None and fraud["transaction_count"] == 0


def test_merchant_b_activity_never_appears_in_merchant_a_results(ro_session: Session) -> None:
    a_declines = {
        r["decline_reason"]: r["declined_count"] for r in _run(ro_session, "get_decline_reasons")["reasons"]
    }
    assert a_declines["DO_NOT_HONOR"] == 1  # B has two DO_NOT_HONOR declines; they must not be counted
    b_window = AnalyticsQuery(start=date(2026, 3, 2), end=date(2026, 3, 2))
    b = _run(ro_session, "get_decline_rate", merchant=B, query=b_window)
    assert b["declined_count"] == 2 and b["transaction_count"] == 3
    assert b["decline_rate"] == pytest.approx(0.6667)


def test_unknown_merchant_raises_not_found(ro_session: Session) -> None:
    with pytest.raises(MerchantNotFoundError):
        _run(ro_session, "get_transaction_volume", merchant="merchant_does_not_exist")


def test_every_registered_tool_returns_a_metric_definition(ro_session: Session) -> None:
    from app.analytics.service import ANALYTICS_FUNCTIONS

    for name in ANALYTICS_FUNCTIONS:
        result = _run(ro_session, name)
        assert result["metric_definition"]["tool"] == name
        assert result["metric_definition"]["assumptions"]
