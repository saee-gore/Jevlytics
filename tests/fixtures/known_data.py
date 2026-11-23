"""Hand-built known-answer fixture for analytics tests.

Every expected value in tests/integration/test_known_fixture_metrics.py is computed by hand from
the rows below. Do not change a row without updating those expectations.

merchant_test_a: America/Los_Angeles, USD and CAD.
merchant_test_b: America/New_York, USD only. Its activity must never appear in A's results.

Local times are America/Los_Angeles for A and America/New_York for B. The UTC offsets are written
explicitly so the boundary tests are unambiguous (March 2026 is PST, UTC-08:00, before 2026-03-08).
"""

from __future__ import annotations

from typing import Any

MERCHANT_A = "merchant_test_a"
MERCHANT_B = "merchant_test_b"

MERCHANTS = [
    {
        "merchant_id": MERCHANT_A,
        "legal_name": "Test Merchant A",
        "vertical": "test",
        "timezone": "America/Los_Angeles",
        "is_synthetic": True,
    },
    {
        "merchant_id": MERCHANT_B,
        "legal_name": "Test Merchant B",
        "vertical": "test",
        "timezone": "America/New_York",
        "is_synthetic": True,
    },
]

USERS = [
    {
        "user_id": "test-analyst-a",
        "merchant_id": MERCHANT_A,
        "role": "ANALYST",
        "display_name": "Test Analyst A",
        "is_active": True,
    },
    {
        "user_id": "test-viewer-a",
        "merchant_id": MERCHANT_A,
        "role": "VIEWER",
        "display_name": "Test Viewer A",
        "is_active": True,
    },
    {
        "user_id": "test-analyst-b",
        "merchant_id": MERCHANT_B,
        "role": "ANALYST",
        "display_name": "Test Analyst B",
        "is_active": True,
    },
]


def _txn(
    tid: str,
    merchant: str,
    ts: str,
    card_type: str,
    network: str,
    amount: str,
    currency: str,
    status: str,
    region: str,
    decline_reason: str | None = None,
    risk_flag: bool = False,
    risk_reason: str | None = None,
    settlement_id: str | None = None,
    settlement_date: str | None = None,
    chargeback_id: str | None = None,
    chargeback_date: str | None = None,
) -> dict[str, Any]:
    return {
        "transaction_id": tid,
        "merchant_id": merchant,
        "transaction_timestamp": ts,
        "card_type": card_type,
        "card_network": network,
        "amount": amount,
        "currency": currency,
        "status": status,
        "decline_reason": decline_reason,
        "region": region,
        "settlement_id": settlement_id,
        "settlement_date": settlement_date,
        "settlement_amount": amount if settlement_id else None,
        "chargeback_id": chargeback_id,
        "chargeback_date": chargeback_date,
        "chargeback_reason": "FRAUD_NOT_RECOGNIZED" if chargeback_id else None,
        "risk_score": 80 if risk_flag else 10,
        "risk_flag": risk_flag,
        "risk_reason": risk_reason,
    }


# Merchant A (local = LA, UTC-08:00 in March 2026)
#   t1  03-01 10:00 local  CREDIT VISA   100.00 USD APPROVED  R1  (chargeback dated 2026-03-20)
#   t2  03-01 23:30 local  DEBIT  MC      50.00 USD DECLINED  R1  INSUFFICIENT_FUNDS, risk flagged
#   t3  03-02 00:30 local  CREDIT AMEX    25.50 USD APPROVED  R2  (UTC is already 03-02 08:30)
#   t4  03-02 12:00 local  DEBIT  VISA   200.00 CAD APPROVED  R2
#   t5  03-03 09:00 local  DEBIT  VISA    10.00 USD DECLINED  R1  DO_NOT_HONOR
#   t6  03-03 09:05 local  DEBIT  VISA    10.00 USD APPROVED  R1
#   t7  03-04 08:00 local  CREDIT VISA    40.00 USD PENDING   R2
#   t8  02-28 23:59 local  CREDIT VISA   999.00 USD APPROVED  R1  (before window)
#   t9  03-05 00:00 local  CREDIT VISA     1.00 USD APPROVED  R1  (after window end 03-04)
#
# Merchant B (local = NY): three transactions on 2026-03-02, which must never leak into A.
TRANSACTIONS: list[dict[str, Any]] = [
    _txn(
        "txn_a_1",
        MERCHANT_A,
        "2026-03-01T10:00:00-08:00",
        "CREDIT",
        "VISA",
        "100.00",
        "USD",
        "APPROVED",
        "R1",
        chargeback_id="cb_a_1",
        chargeback_date="2026-03-20",
        settlement_id="stl_a_1",
        settlement_date="2026-03-02",
    ),
    _txn(
        "txn_a_2",
        MERCHANT_A,
        "2026-03-01T23:30:00-08:00",
        "DEBIT",
        "MASTERCARD",
        "50.00",
        "USD",
        "DECLINED",
        "R1",
        decline_reason="INSUFFICIENT_FUNDS",
        risk_flag=True,
        risk_reason="VELOCITY_BREACH",
    ),
    _txn(
        "txn_a_3",
        MERCHANT_A,
        "2026-03-02T00:30:00-08:00",
        "CREDIT",
        "AMEX",
        "25.50",
        "USD",
        "APPROVED",
        "R2",
    ),
    _txn(
        "txn_a_4",
        MERCHANT_A,
        "2026-03-02T12:00:00-08:00",
        "DEBIT",
        "VISA",
        "200.00",
        "CAD",
        "APPROVED",
        "R2",
    ),
    _txn(
        "txn_a_5",
        MERCHANT_A,
        "2026-03-03T09:00:00-08:00",
        "DEBIT",
        "VISA",
        "10.00",
        "USD",
        "DECLINED",
        "R1",
        decline_reason="DO_NOT_HONOR",
    ),
    _txn(
        "txn_a_6",
        MERCHANT_A,
        "2026-03-03T09:05:00-08:00",
        "DEBIT",
        "VISA",
        "10.00",
        "USD",
        "APPROVED",
        "R1",
    ),
    _txn(
        "txn_a_7",
        MERCHANT_A,
        "2026-03-04T08:00:00-08:00",
        "CREDIT",
        "VISA",
        "40.00",
        "USD",
        "PENDING",
        "R2",
    ),
    _txn(
        "txn_a_8",
        MERCHANT_A,
        "2026-02-28T23:59:00-08:00",
        "CREDIT",
        "VISA",
        "999.00",
        "USD",
        "APPROVED",
        "R1",
    ),
    _txn(
        "txn_a_9",
        MERCHANT_A,
        "2026-03-05T00:00:00-08:00",
        "CREDIT",
        "VISA",
        "1.00",
        "USD",
        "APPROVED",
        "R1",
    ),
    _txn(
        "txn_b_1",
        MERCHANT_B,
        "2026-03-02T10:00:00-05:00",
        "CREDIT",
        "VISA",
        "5000.00",
        "USD",
        "APPROVED",
        "R1",
    ),
    _txn(
        "txn_b_2",
        MERCHANT_B,
        "2026-03-02T11:00:00-05:00",
        "DEBIT",
        "VISA",
        "70.00",
        "USD",
        "DECLINED",
        "R1",
        decline_reason="DO_NOT_HONOR",
    ),
    _txn(
        "txn_b_3",
        MERCHANT_B,
        "2026-03-02T12:00:00-05:00",
        "DEBIT",
        "VISA",
        "70.00",
        "USD",
        "DECLINED",
        "R1",
        decline_reason="DO_NOT_HONOR",
    ),
]

SETTLEMENTS: list[dict[str, Any]] = [
    {
        "settlement_id": "stl_a_1",
        "merchant_id": MERCHANT_A,
        "settlement_date": "2026-03-02",
        "currency": "USD",
        "gross_amount": "100.00",
        "transaction_count": 1,
    },
    {
        "settlement_id": "stl_a_2",
        "merchant_id": MERCHANT_A,
        "settlement_date": "2026-03-05",
        "currency": "USD",
        "gross_amount": "25.50",
        "transaction_count": 1,
    },
]

CHARGEBACKS: list[dict[str, Any]] = [
    {
        "chargeback_id": "cb_a_1",
        "merchant_id": MERCHANT_A,
        "transaction_id": "txn_a_1",
        "chargeback_date": "2026-03-20",
        "amount": "100.00",
        "currency": "USD",
        "reason": "FRAUD_NOT_RECOGNIZED",
    },
]

# Hand-computed expectations for the window 2026-03-01 .. 2026-03-04 (LA local dates), merchant A.
WINDOW_START = "2026-03-01"
WINDOW_END = "2026-03-04"
EXPECTED: dict[str, Any] = {
    "volume_by_currency": {"CAD": ("1", "200.00"), "USD": ("3", "135.50")},
    "status_counts": {"APPROVED": 4, "DECLINED": 2, "PENDING": 1},
    "decline_reasons": {"DO_NOT_HONOR": 1, "INSUFFICIENT_FUNDS": 1},
    "decline_rate_overall": "0.3333",  # 2 declined / 6 attempts
    "decline_rate_by_network": {"VISA": "0.2500", "MASTERCARD": "1.0000", "AMEX": "0.0000"},
    "settled_usd": ("1", "100.00"),
    "chargeback_rate": "0.2500",  # 1 chargeback (t1) / 4 approved
    "card_type_debit_usd": {"approved": 1, "declined": 2, "rate": "0.6667", "volume": "10.00"},
    "card_type_credit_usd": {"approved": 2, "declined": 0, "rate": "0.0000", "volume": "125.50"},
    "region_r1_usd": ("2", "110.00"),
    "region_r2_usd": ("1", "25.50"),
    "region_r2_cad": ("1", "200.00"),
    "fraud_flagged": 1,
    "fraud_total": 7,
}
