"""Least-privilege roles, and SQL results cross-checked against an independent CSV computation."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from app.analytics.service import (
    AnalyticsQuery,
    get_card_type_performance,
    get_chargeback_rate,
    get_settlement_volume,
    get_transaction_volume,
)
from tests.integration.conftest import DbEnv

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


# --- Database role boundaries -----------------------------------------------------------------------


def _expect_denied(session: Session, sql: str) -> None:
    with pytest.raises((ProgrammingError, DBAPIError)) as info:
        session.execute(text(sql))
    assert "permission denied" in str(info.value).lower() or "read-only" in str(info.value).lower()
    session.rollback()


def test_analytics_role_cannot_write_tenant_data(ro_session: Session) -> None:
    _expect_denied(ro_session, "UPDATE transactions SET amount = 0")
    _expect_denied(ro_session, "DELETE FROM transactions")
    _expect_denied(
        ro_session,
        "INSERT INTO merchants (merchant_id, legal_name, vertical, timezone) VALUES ('x','x','x','UTC')",
    )


def test_analytics_role_cannot_read_users_or_audit(ro_session: Session) -> None:
    _expect_denied(ro_session, "SELECT * FROM users")
    _expect_denied(ro_session, "SELECT * FROM audit_events")


def test_analytics_connection_is_read_only_by_default(ro_session: Session, db_env: DbEnv) -> None:
    # Even a role with write grants would be blocked by default_transaction_read_only=on.
    row = ro_session.execute(text("SHOW default_transaction_read_only")).scalar()
    assert row == "on"


def test_application_role_cannot_alter_transactions(app_db_session: Session) -> None:
    _expect_denied(app_db_session, "UPDATE transactions SET status = 'APPROVED'")
    _expect_denied(app_db_session, "DELETE FROM chargebacks")


def test_application_role_can_append_audit_only(app_db_session: Session) -> None:
    rows = app_db_session.execute(text("SELECT count(*) FROM users")).scalar()
    assert rows and rows > 0
    app_db_session.rollback()
    _expect_denied(app_db_session, "UPDATE audit_events SET response_status = 'answered'")


def test_owner_role_is_not_used_by_the_application(app_settings) -> None:  # type: ignore[no-untyped-def]
    assert "merchant_owner" not in app_settings.database_url.get_secret_value()
    assert "merchant_owner" not in app_settings.analytics_database_url.get_secret_value()


# --- Independent reference computation over the generated CSVs --------------------------------------


def _read(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _local_date(ts: str) -> date:
    # Timestamps are written in the merchant's local offset, so the date prefix is the local date.
    return date.fromisoformat(ts[:10])


def _transactions(merchant: str) -> list[dict[str, str]]:
    return _read(f"transactions_{merchant}.csv")


def test_card_type_decline_rate_matches_csv_reference(ro_session: Session) -> None:
    start, end = date(2026, 10, 1), date(2026, 10, 31)
    rows = [
        t for t in _transactions("merchant_001") if start <= _local_date(t["transaction_timestamp"]) <= end
    ]
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"approved": 0, "declined": 0})
    for t in rows:
        if t["status"] in ("APPROVED", "DECLINED"):
            key = "approved" if t["status"] == "APPROVED" else "declined"
            counts[(t["card_type"], t["currency"])][key] += 1

    result = get_card_type_performance(ro_session, "merchant_001", AnalyticsQuery(start=start, end=end))
    for bucket in result["by_card_type_and_currency"]:
        expected = counts[(bucket["card_type"], bucket["currency"])]
        assert bucket["approved_count"] == expected["approved"]
        assert bucket["declined_count"] == expected["declined"]
        total = expected["approved"] + expected["declined"]
        expected_rate = round(expected["declined"] / total, 4) if total else None
        assert (
            bucket["decline_rate"] == pytest.approx(expected_rate)
            if expected_rate is not None
            else bucket["decline_rate"] is None
        )


def test_debit_spike_is_visible_in_sql_results(ro_session: Session) -> None:
    # The generator adds a decline spike for DEBIT cards between 2026-10-01 and 2026-10-10.
    spike = get_card_type_performance(
        ro_session, "merchant_001", AnalyticsQuery(start=date(2026, 10, 1), end=date(2026, 10, 10))
    )
    calm = get_card_type_performance(
        ro_session, "merchant_001", AnalyticsQuery(start=date(2026, 9, 1), end=date(2026, 9, 30))
    )

    def debit_usd(result: dict) -> float:  # type: ignore[type-arg]
        return next(
            b["decline_rate"] for b in result["by_card_type_and_currency"] if b["card_type"] == "DEBIT"
        )

    assert debit_usd(spike) > debit_usd(calm) + 0.05


def test_merchant_003_volume_per_currency_matches_csv(ro_session: Session) -> None:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    counts: dict[str, int] = defaultdict(int)
    for t in _transactions("merchant_003"):
        if t["status"] == "APPROVED":
            totals[t["currency"]] += Decimal(t["amount"])
            counts[t["currency"]] += 1
    start, end = date(2026, 7, 24), date(2026, 11, 20)
    result = get_transaction_volume(ro_session, "merchant_003", AnalyticsQuery(start=start, end=end))
    for row in result["by_currency"]:
        assert row["approved_count"] == counts[row["currency"]]
        assert Decimal(row["approved_volume"]) == totals[row["currency"]].quantize(Decimal("0.01"))
    assert set(totals) == {"GBP", "EUR", "USD"}  # currencies are never merged


def test_merchant_001_settlement_volume_matches_settlements_csv(ro_session: Session) -> None:
    rows = [
        s for s in _read("settlements.csv") if s["merchant_id"] == "merchant_001" and s["currency"] == "USD"
    ]
    expected = sum((Decimal(s["gross_amount"]) for s in rows), Decimal("0"))
    result = get_settlement_volume(
        ro_session,
        "merchant_001",
        AnalyticsQuery(start=date(2026, 7, 24), end=date(2026, 11, 20), currency="USD"),
    )
    assert Decimal(result["by_currency"][0]["settled_volume"]) == expected.quantize(Decimal("0.01"))


def test_merchant_002_chargeback_rate_matches_csv_cohort(ro_session: Session) -> None:
    start, end = date(2026, 7, 24), date(2026, 11, 20)
    approved_ids = {t["transaction_id"] for t in _transactions("merchant_002") if t["status"] == "APPROVED"}
    chargebacks = [c for c in _read("chargebacks.csv") if c["merchant_id"] == "merchant_002"]
    cohort = [c for c in chargebacks if c["transaction_id"] in approved_ids]
    result = get_chargeback_rate(ro_session, "merchant_002", AnalyticsQuery(start=start, end=end))
    assert result["chargeback_count"] == len(cohort)
    assert result["approved_transaction_count"] == len(approved_ids)


def test_seeded_database_row_counts_match_csv_files(admin_session: Session) -> None:
    counts = admin_session.execute(
        text(
            "SELECT (SELECT count(*) FROM transactions), (SELECT count(*) FROM settlements), "
            "(SELECT count(*) FROM chargebacks)"
        )
    ).one()
    txn_total = sum(len(_transactions(m)) for m in ("merchant_001", "merchant_002", "merchant_003"))
    # The known fixture adds 12 transactions on top of the demo data.
    assert counts[0] == txn_total + 12
    assert counts[1] == len(_read("settlements.csv")) + 2
    assert counts[2] == len(_read("chargebacks.csv")) + 1


def test_manifest_hashes_still_match_files() -> None:
    import json

    manifest = json.loads((DATA / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel, expected in manifest["files"].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, rel


def test_engine_helper_is_importable_for_admin_checks(db_env: DbEnv) -> None:
    engine = create_engine(db_env.admin_url.replace("postgresql://", "postgresql+psycopg://", 1))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar() == 1
    engine.dispose()
