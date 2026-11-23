#!/usr/bin/env python3
"""Deterministic generator for SYNTHETIC merchant card-transaction demo data.

DEMO DATA ONLY. Nothing generated here is a real merchant, person, account or credential.
The output contains no PAN, CVV/CVC, PIN, PIN block, track data, names or contact details.

Usage:
    python scripts/generate_dummy_data.py              # (re)write data/ files
    python scripts/generate_dummy_data.py --check      # verify data/ matches data/MANIFEST.json

Reproducibility: a fixed seed, fixed dates, and deterministic iteration order. The manifest
records a SHA-256 for every generated file so that regeneration on the same Python version can be
verified. Floating-point lognormal draws are the only platform-sensitive step; the manifest is the
authority if they ever differ.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

SEED = 20261120
START_DATE = date(2026, 7, 24)
DAYS = 120
END_DATE = START_DATE + timedelta(days=DAYS - 1)  # 2026-11-20 (inclusive)
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "MANIFEST.json"

NETWORKS: tuple[tuple[str, float], ...] = (
    ("VISA", 0.50),
    ("MASTERCARD", 0.32),
    ("AMEX", 0.12),
    ("DISCOVER", 0.06),
)
DECLINE_REASONS: tuple[tuple[str, float], ...] = (
    ("INSUFFICIENT_FUNDS", 0.30),
    ("DO_NOT_HONOR", 0.28),
    ("EXPIRED_CARD", 0.12),
    ("ISSUER_UNAVAILABLE", 0.15),
    ("SUSPECTED_FRAUD", 0.15),
)
CHARGEBACK_REASONS: tuple[tuple[str, float], ...] = (
    ("FRAUD_NOT_RECOGNIZED", 0.35),
    ("PRODUCT_NOT_RECEIVED", 0.25),
    ("DUPLICATE_CHARGE", 0.20),
    ("SUBSCRIPTION_CANCELLED", 0.20),
)
RISK_REASONS: tuple[str, ...] = (
    "VELOCITY_BREACH",
    "GEO_MISMATCH",
    "UNUSUAL_AMOUNT",
    "NEW_DEVICE_PATTERN",
)
# Hour-of-day weights (local time): daytime-heavy, with an evening shoulder.
HOUR_WEIGHTS: tuple[float, ...] = (
    0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.8, 1.2, 1.5, 1.6, 1.6,
    1.5, 1.5, 1.6, 1.6, 1.5, 1.4, 1.5, 1.6, 1.4, 1.0, 0.7, 0.4,
)  # fmt: skip


@dataclass(frozen=True)
class RegionSpec:
    code: str
    currency: str
    weight: float
    decline_rate: float


@dataclass(frozen=True)
class Spike:
    """A temporary increase in declines for one card type in a local-date window."""

    card_type: str
    start: date
    end: date
    extra_decline_rate: float
    reason: str


@dataclass(frozen=True)
class MerchantSpec:
    merchant_id: str
    legal_name: str
    vertical: str
    timezone: str
    credit_share: float
    debit_extra_decline: float
    regions: tuple[RegionSpec, ...]
    transaction_count: int
    amount_mu: float
    amount_sigma: float
    chargeback_rate: float
    weekday_weights: tuple[float, ...]
    spike: Spike | None = None


MERCHANTS: tuple[MerchantSpec, ...] = (
    MerchantSpec(
        merchant_id="merchant_001",
        legal_name="Northwind Outdoor Supply (fictional)",
        vertical="retail_ecommerce",
        timezone="America/Los_Angeles",
        credit_share=0.62,
        debit_extra_decline=0.03,
        regions=(
            RegionSpec("US-WEST", "USD", 0.45, 0.04),
            RegionSpec("US-EAST", "USD", 0.35, 0.05),
            RegionSpec("US-CENTRAL", "USD", 0.20, 0.045),
        ),
        transaction_count=2900,
        amount_mu=4.0,
        amount_sigma=0.9,
        chargeback_rate=0.010,
        weekday_weights=(1.0, 0.9, 0.95, 1.0, 1.15, 1.3, 1.2),
        spike=Spike(
            card_type="DEBIT",
            start=date(2026, 10, 1),
            end=date(2026, 10, 10),
            extra_decline_rate=0.20,
            reason="DO_NOT_HONOR",
        ),
    ),
    MerchantSpec(
        merchant_id="merchant_002",
        legal_name="Lumen Subscription Services (fictional)",
        vertical="subscription_services",
        timezone="America/New_York",
        credit_share=0.70,
        debit_extra_decline=0.05,
        regions=(
            RegionSpec("US-EAST", "USD", 0.55, 0.035),
            RegionSpec("US-WEST", "USD", 0.25, 0.040),
            RegionSpec("CA-ONTARIO", "CAD", 0.20, 0.045),
        ),
        transaction_count=2600,
        amount_mu=2.9,
        amount_sigma=0.5,
        chargeback_rate=0.020,
        weekday_weights=(1.1, 1.0, 1.0, 1.0, 1.0, 0.9, 1.0),
    ),
    MerchantSpec(
        merchant_id="merchant_003",
        legal_name="Harbor Stays Hospitality (fictional)",
        vertical="travel_hospitality",
        timezone="Europe/London",
        credit_share=0.58,
        debit_extra_decline=0.02,
        regions=(
            RegionSpec("UK", "GBP", 0.40, 0.050),
            RegionSpec("EU-WEST", "EUR", 0.35, 0.070),
            RegionSpec("US-EAST", "USD", 0.25, 0.030),
        ),
        transaction_count=2700,
        amount_mu=5.0,
        amount_sigma=0.8,
        chargeback_rate=0.008,
        weekday_weights=(0.8, 0.8, 0.9, 1.0, 1.2, 1.5, 1.4),
    ),
)

DEMO_USERS: tuple[tuple[str, str, str, str], ...] = (
    ("demo-analyst-001", "merchant_001", "ANALYST", "Demo Analyst 001"),
    ("demo-viewer-001", "merchant_001", "VIEWER", "Demo Viewer 001"),
    ("demo-analyst-002", "merchant_002", "ANALYST", "Demo Analyst 002"),
    ("demo-analyst-003", "merchant_003", "ANALYST", "Demo Analyst 003"),
)

TRANSACTION_FIELDS = [
    "transaction_id",
    "merchant_id",
    "transaction_timestamp",
    "card_type",
    "card_network",
    "amount",
    "currency",
    "status",
    "decline_reason",
    "region",
    "settlement_id",
    "settlement_date",
    "settlement_amount",
    "chargeback_id",
    "chargeback_date",
    "chargeback_reason",
    "risk_score",
    "risk_flag",
    "risk_reason",
]
SETTLEMENT_FIELDS = [
    "settlement_id",
    "merchant_id",
    "settlement_date",
    "currency",
    "gross_amount",
    "transaction_count",
]
CHARGEBACK_FIELDS = [
    "chargeback_id",
    "merchant_id",
    "transaction_id",
    "chargeback_date",
    "amount",
    "currency",
    "reason",
]
MERCHANT_FIELDS = ["merchant_id", "legal_name", "vertical", "timezone", "is_synthetic"]
USER_FIELDS = ["user_id", "merchant_id", "role", "display_name", "is_active"]


def weighted_choice(rng: random.Random, options: tuple[tuple[str, float], ...]) -> str:
    names = [name for name, _ in options]
    weights = [weight for _, weight in options]
    return rng.choices(names, weights=weights, k=1)[0]


def money(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def generate() -> dict[str, list[dict[str, str]]]:
    rng = random.Random(SEED)  # noqa: S311 - reproducible synthetic data, not security-sensitive
    hour_choices = list(range(24))
    tables: dict[str, list[dict[str, str]]] = {
        "merchants": [],
        "transactions": [],
        "settlements": [],
        "chargebacks": [],
        "users": [],
    }

    for spec in MERCHANTS:
        tz = ZoneInfo(spec.timezone)
        tables["merchants"].append(
            {
                "merchant_id": spec.merchant_id,
                "legal_name": spec.legal_name,
                "vertical": spec.vertical,
                "timezone": spec.timezone,
                "is_synthetic": "true",
            }
        )
        merchant_no = spec.merchant_id.split("_")[1]
        region_names = [r.code for r in spec.regions]
        region_weights = [r.weight for r in spec.regions]
        region_by_code = {r.code: r for r in spec.regions}
        day_weights = [
            spec.weekday_weights[(START_DATE + timedelta(days=i)).weekday()] * (1 + 0.003 * i)
            for i in range(DAYS)
        ]

        merchant_txns: list[dict[str, str]] = []
        for n in range(1, spec.transaction_count + 1):
            day_index = rng.choices(range(DAYS), weights=day_weights, k=1)[0]
            local_date = START_DATE + timedelta(days=day_index)
            hour = rng.choices(hour_choices, weights=HOUR_WEIGHTS, k=1)[0]
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            local_ts = datetime.combine(local_date, time(hour, minute, second), tzinfo=tz)

            card_type = "CREDIT" if rng.random() < spec.credit_share else "DEBIT"
            network = weighted_choice(rng, NETWORKS)
            region = rng.choices(region_names, weights=region_weights, k=1)[0]
            region_spec = region_by_code[region]
            currency = region_spec.currency
            amount = money(rng.lognormvariate(spec.amount_mu, spec.amount_sigma))

            decline_p = region_spec.decline_rate
            if card_type == "DEBIT":
                decline_p += spec.debit_extra_decline
            spike_reason: str | None = None
            if (
                spec.spike is not None
                and card_type == spec.spike.card_type
                and spec.spike.start <= local_date <= spec.spike.end
            ):
                decline_p += spec.spike.extra_decline_rate
                spike_reason = spec.spike.reason
            decline_p = min(decline_p, 0.95)

            draw = rng.random()
            pending_window = local_date >= END_DATE - timedelta(days=1)
            decline_reason: str | None = None
            if draw < decline_p:
                status = "DECLINED"
                if spike_reason is not None and rng.random() < 0.8:
                    decline_reason = spike_reason
                else:
                    decline_reason = weighted_choice(rng, DECLINE_REASONS)
            elif pending_window and rng.random() < 0.5:
                status = "PENDING"
            else:
                status = "APPROVED"
                lifecycle = rng.random()
                if local_date < END_DATE - timedelta(days=10):
                    if lifecycle < 0.012:
                        status = "REVERSED"
                    elif lifecycle < 0.032:
                        status = "REFUNDED"

            risk_score = rng.randint(0, 60)
            if decline_reason == "SUSPECTED_FRAUD":
                risk_score += 25
            risk_flag = risk_score >= 75
            risk_reason = rng.choice(RISK_REASONS) if risk_flag else ""

            txn_id = f"txn_{merchant_no}_{n:06d}"
            row: dict[str, str] = {
                "transaction_id": txn_id,
                "merchant_id": spec.merchant_id,
                "transaction_timestamp": local_ts.isoformat(timespec="seconds"),
                "card_type": card_type,
                "card_network": network,
                "amount": str(amount),
                "currency": currency,
                "status": status,
                "decline_reason": decline_reason or "",
                "region": region,
                "settlement_id": "",
                "settlement_date": "",
                "settlement_amount": "",
                "chargeback_id": "",
                "chargeback_date": "",
                "chargeback_reason": "",
                "risk_score": str(risk_score),
                "risk_flag": "true" if risk_flag else "false",
                "risk_reason": risk_reason,
            }
            merchant_txns.append(row)

            # Chargebacks: only approved transactions old enough to be disputed in the window.
            if status == "APPROVED" and local_date <= END_DATE - timedelta(days=20):
                if rng.random() < spec.chargeback_rate:
                    cb_date = local_date + timedelta(days=rng.randint(14, 60))
                    cb_reason = weighted_choice(rng, CHARGEBACK_REASONS)
                    if cb_date <= END_DATE:
                        cb_id = f"cb_{merchant_no}_{len(tables['chargebacks']) + 1:05d}"
                        row["chargeback_id"] = cb_id
                        row["chargeback_date"] = cb_date.isoformat()
                        row["chargeback_reason"] = cb_reason
                        tables["chargebacks"].append(
                            {
                                "chargeback_id": cb_id,
                                "merchant_id": spec.merchant_id,
                                "transaction_id": txn_id,
                                "chargeback_date": cb_date.isoformat(),
                                "amount": str(amount),
                                "currency": currency,
                                "reason": cb_reason,
                            }
                        )

        # Settlements: approved transactions settle the next local business day (T+1 here).
        # Only settlements whose date falls inside the data window are materialised.
        buckets: dict[tuple[date, str], list[dict[str, str]]] = {}
        for row in merchant_txns:
            if row["status"] != "APPROVED":
                continue
            local_day = datetime.fromisoformat(row["transaction_timestamp"]).date()
            settle_day = local_day + timedelta(days=1)
            if settle_day > END_DATE:
                continue
            buckets.setdefault((settle_day, row["currency"]), []).append(row)

        for (settle_day, currency), rows in sorted(buckets.items()):
            settlement_id = f"stl_{merchant_no}_{settle_day:%Y%m%d}_{currency}"
            gross = sum((Decimal(r["amount"]) for r in rows), Decimal("0.00"))
            for r in rows:
                r["settlement_id"] = settlement_id
                r["settlement_date"] = settle_day.isoformat()
                r["settlement_amount"] = r["amount"]
            tables["settlements"].append(
                {
                    "settlement_id": settlement_id,
                    "merchant_id": spec.merchant_id,
                    "settlement_date": settle_day.isoformat(),
                    "currency": currency,
                    "gross_amount": str(gross.quantize(Decimal("0.01"))),
                    "transaction_count": str(len(rows)),
                }
            )

        merchant_txns.sort(key=lambda r: (r["transaction_timestamp"], r["transaction_id"]))
        tables["transactions"].extend(merchant_txns)

    for user_id, merchant_id, role, display_name in DEMO_USERS:
        tables["users"].append(
            {
                "user_id": user_id,
                "merchant_id": merchant_id,
                "role": role,
                "display_name": display_name,
                "is_active": "true",
            }
        )
    return tables


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def output_files(
    tables: dict[str, list[dict[str, str]]],
) -> dict[Path, tuple[list[str], list[dict[str, str]]]]:
    files: dict[Path, tuple[list[str], list[dict[str, str]]]] = {
        DATA_DIR / "merchants.csv": (MERCHANT_FIELDS, tables["merchants"]),
        DATA_DIR / "settlements.csv": (
            SETTLEMENT_FIELDS,
            sorted(tables["settlements"], key=lambda r: r["settlement_id"]),
        ),
        DATA_DIR / "chargebacks.csv": (
            CHARGEBACK_FIELDS,
            sorted(tables["chargebacks"], key=lambda r: r["chargeback_id"]),
        ),
        DATA_DIR / "users.csv": (USER_FIELDS, tables["users"]),
    }
    for spec in MERCHANTS:
        rows = [r for r in tables["transactions"] if r["merchant_id"] == spec.merchant_id]
        files[DATA_DIR / f"transactions_{spec.merchant_id}.csv"] = (TRANSACTION_FIELDS, rows)
    return files


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_all() -> dict[str, str]:
    tables = generate()
    hashes: dict[str, str] = {}
    for path, (fields, rows) in output_files(tables).items():
        write_csv(path, fields, rows)
        hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
    manifest = {
        "generator": "scripts/generate_dummy_data.py",
        "seed": SEED,
        "start_date": START_DATE.isoformat(),
        "end_date": END_DATE.isoformat(),
        "synthetic": True,
        "files": dict(sorted(hashes.items())),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return hashes


def check() -> int:
    if not MANIFEST_PATH.exists():
        print("MANIFEST.json missing; run without --check first.", file=sys.stderr)
        return 2
    expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["files"]
    tables = generate()
    failures = 0
    for path, (fields, rows) in output_files(tables).items():
        rel = path.relative_to(ROOT).as_posix()
        tmp = path.with_suffix(".check.tmp")
        write_csv(tmp, fields, rows)
        actual = sha256(tmp)
        tmp.unlink()
        if expected.get(rel) != actual:
            failures += 1
            print(f"MISMATCH {rel}", file=sys.stderr)
    print("OK: data matches manifest" if failures == 0 else f"{failures} file(s) differ")
    return 0 if failures == 0 else 1


def summary(tables: dict[str, list[dict[str, str]]]) -> str:
    txns = tables["transactions"]
    counts: dict[str, int] = {}
    for row in txns:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = [
        f"merchants={len(tables['merchants'])} transactions={len(txns)} "
        f"settlements={len(tables['settlements'])} chargebacks={len(tables['chargebacks'])}",
        "statuses=" + json.dumps(dict(sorted(counts.items()))),
        f"window={START_DATE.isoformat()}..{END_DATE.isoformat()} ({DAYS} days) seed={SEED}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="verify files against data/MANIFEST.json")
    args = parser.parse_args()
    if args.check:
        return check()
    write_all()
    print(summary(generate()))
    print(f"wrote files to {DATA_DIR.relative_to(ROOT)}/ and manifest {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
