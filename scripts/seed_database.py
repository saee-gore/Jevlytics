#!/usr/bin/env python3
"""Idempotent seeder for SYNTHETIC demo data.

Requires MIGRATION_DATABASE_URL (privileged owner role). Run after `alembic upgrade head`.

    alembic upgrade head
    python scripts/seed_database.py
    python scripts/seed_database.py          # safe to re-run: existing rows are skipped

Idempotency: every insert uses ON CONFLICT (primary key) DO NOTHING. Re-running therefore never
duplicates rows. It also never UPDATEs: if a CSV changes after seeding, drop and re-seed the demo
schema (`alembic downgrade base && alembic upgrade head`) rather than patching in place.

Safety: refuses to run when APP_ENV=production unless --allow-production is given, and verifies
data/MANIFEST.json by default so that only the generated demo files are loaded.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import Engine, create_engine, func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import (  # noqa: E402
    Chargeback,
    Merchant,
    Settlement,
    Transaction,
    User,
)

DATA_DIR = ROOT / "data"
BATCH_SIZE = 1000


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _opt(value: str) -> str | None:
    return value if value != "" else None


def _opt_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _opt_dec(value: str) -> Decimal | None:
    return Decimal(value) if value else None


def read_rows(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def merchant_rows() -> Iterable[dict[str, Any]]:
    for r in read_rows("merchants.csv"):
        yield {
            "merchant_id": r["merchant_id"],
            "legal_name": r["legal_name"],
            "vertical": r["vertical"],
            "timezone": r["timezone"],
            "is_synthetic": _bool(r["is_synthetic"]),
        }


def user_rows() -> Iterable[dict[str, Any]]:
    for r in read_rows("users.csv"):
        yield {
            "user_id": r["user_id"],
            "merchant_id": r["merchant_id"],
            "role": r["role"],
            "display_name": r["display_name"],
            "is_active": _bool(r["is_active"]),
        }


def settlement_rows() -> Iterable[dict[str, Any]]:
    for r in read_rows("settlements.csv"):
        yield {
            "settlement_id": r["settlement_id"],
            "merchant_id": r["merchant_id"],
            "settlement_date": date.fromisoformat(r["settlement_date"]),
            "currency": r["currency"],
            "gross_amount": Decimal(r["gross_amount"]),
            "transaction_count": int(r["transaction_count"]),
        }


def transaction_rows() -> Iterable[dict[str, Any]]:
    for name in sorted(p.name for p in DATA_DIR.glob("transactions_merchant_*.csv")):
        for r in read_rows(name):
            yield {
                "transaction_id": r["transaction_id"],
                "merchant_id": r["merchant_id"],
                "transaction_timestamp": datetime.fromisoformat(r["transaction_timestamp"]),
                "card_type": r["card_type"],
                "card_network": r["card_network"],
                "amount": Decimal(r["amount"]),
                "currency": r["currency"],
                "status": r["status"],
                "decline_reason": _opt(r["decline_reason"]),
                "region": r["region"],
                "settlement_id": _opt(r["settlement_id"]),
                "settlement_date": _opt_date(r["settlement_date"]),
                "settlement_amount": _opt_dec(r["settlement_amount"]),
                "chargeback_id": _opt(r["chargeback_id"]),
                "chargeback_date": _opt_date(r["chargeback_date"]),
                "chargeback_reason": _opt(r["chargeback_reason"]),
                "risk_score": int(r["risk_score"]),
                "risk_flag": _bool(r["risk_flag"]),
                "risk_reason": _opt(r["risk_reason"]),
            }


def chargeback_rows() -> Iterable[dict[str, Any]]:
    for r in read_rows("chargebacks.csv"):
        yield {
            "chargeback_id": r["chargeback_id"],
            "merchant_id": r["merchant_id"],
            "transaction_id": r["transaction_id"],
            "chargeback_date": date.fromisoformat(r["chargeback_date"]),
            "amount": Decimal(r["amount"]),
            "currency": r["currency"],
            "reason": r["reason"],
        }


def _batched(rows: Iterable[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert_idempotent(session: Session, model: type, rows: Iterable[dict[str, Any]]) -> int:
    attempted = 0
    for batch in _batched(rows):
        stmt = insert(model.__table__).values(batch).on_conflict_do_nothing()  # type: ignore[attr-defined]
        session.execute(stmt)
        attempted += len(batch)
    return attempted


def seed(engine: Engine) -> dict[str, int]:
    """Insert demo rows in dependency order. Returns attempted-row counts per table."""
    attempted: dict[str, int] = {}
    with Session(engine) as session, session.begin():
        attempted["merchants"] = _insert_idempotent(session, Merchant, merchant_rows())
        attempted["users"] = _insert_idempotent(session, User, user_rows())
        attempted["settlements"] = _insert_idempotent(session, Settlement, settlement_rows())
        attempted["transactions"] = _insert_idempotent(session, Transaction, transaction_rows())
        attempted["chargebacks"] = _insert_idempotent(session, Chargeback, chargeback_rows())
    return attempted


def table_counts(engine: Engine) -> dict[str, int]:
    with Session(engine) as session:
        return {
            "merchants": session.scalar(select(func.count()).select_from(Merchant)) or 0,
            "users": session.scalar(select(func.count()).select_from(User)) or 0,
            "settlements": session.scalar(select(func.count()).select_from(Settlement)) or 0,
            "transactions": session.scalar(select(func.count()).select_from(Transaction)) or 0,
            "chargebacks": session.scalar(select(func.count()).select_from(Chargeback)) or 0,
        }


def verify_manifest() -> None:
    import hashlib

    manifest = json.loads((DATA_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    for rel, expected in manifest["files"].items():
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"Refusing to seed: {rel} does not match data/MANIFEST.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--skip-manifest-check", action="store_true")
    args = parser.parse_args()

    if os.environ.get("APP_ENV", "development").lower() == "production" and not args.allow_production:
        print("Refusing to seed demo data when APP_ENV=production.", file=sys.stderr)
        return 2
    url = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not url:
        print("MIGRATION_DATABASE_URL is required (privileged role).", file=sys.stderr)
        return 2
    if not args.skip_manifest_check:
        verify_manifest()

    engine = create_engine(url)
    attempted = seed(engine)
    print("rows attempted:", json.dumps(attempted, sort_keys=True))
    print("table counts  :", json.dumps(table_counts(engine), sort_keys=True))
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
