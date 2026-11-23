"""Deterministic analytics functions. Each returns a JSON-ready dict of AGGREGATES only.

Every public function takes merchant_id as its FIRST explicit argument. Callers must pass the
merchant_id resolved from the authenticated server context. This module never reads a merchant
identifier from user input.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics import queries as q
from app.analytics.metrics import (
    definition_as_dict,
    local_window_to_utc,
    money_str,
    rate_float,
    safe_rate,
)


class MerchantNotFoundError(LookupError):
    """Raised when the trusted merchant_id has no row. Reported to clients as a generic error."""


@dataclass(frozen=True)
class AnalyticsQuery:
    """Validated, typed filters. Built by the orchestration layer from Pydantic models."""

    start: date
    end: date
    card_type: str | None = None
    card_network: str | None = None
    currency: str | None = None
    region: str | None = None
    status: str | None = None


def _merchant_timezone(session: Session, merchant_id: str) -> str:
    row = session.execute(text(q.MERCHANT_TIMEZONE), {"merchant_id": merchant_id}).first()
    if row is None:
        raise MerchantNotFoundError("merchant not found")
    return str(row.timezone)


def _params(merchant_id: str, tz: str, query: AnalyticsQuery) -> dict[str, Any]:
    start_utc, end_utc = local_window_to_utc(tz, query.start, query.end)
    return {
        "merchant_id": merchant_id,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "card_type": query.card_type,
        "card_network": query.card_network,
        "currency": query.currency,
        "region": query.region,
        "status": query.status,
        "tz": tz,
    }


def _filters_echo(query: AnalyticsQuery) -> dict[str, Any]:
    return {
        "date_range": {"start": query.start.isoformat(), "end": query.end.isoformat()},
        "card_type": query.card_type,
        "card_network": query.card_network,
        "currency": query.currency,
        "region": query.region,
        "status": query.status,
    }


def _rows(session: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in session.execute(text(sql), params).mappings().all()]


def _scalar_int(session: Session, sql: str, params: dict[str, Any], key: str) -> int:
    row = session.execute(text(sql), params).mappings().first()
    return int(row[key]) if row and row[key] is not None else 0


# --- Tool implementations -------------------------------------------------------------------------


def get_transaction_volume(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    rows = _rows(session, q.TRANSACTION_VOLUME_BY_CURRENCY, _params(merchant_id, tz, query))
    by_currency = [
        {
            "currency": r["currency"],
            "approved_count": int(r["approved_count"]),
            "approved_volume": money_str(Decimal(r["approved_volume"])),
        }
        for r in rows
    ]
    return {
        "filters": _filters_echo(query),
        "by_currency": by_currency,
        "total_approved_count": sum(item["approved_count"] for item in by_currency),
    }


def get_transaction_count(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    rows = _rows(session, q.TRANSACTION_COUNT_BY_STATUS, _params(merchant_id, tz, query))
    by_status = [{"status": r["status"], "transaction_count": int(r["transaction_count"])} for r in rows]
    return {
        "filters": _filters_echo(query),
        "by_status": by_status,
        "total_transaction_count": sum(item["transaction_count"] for item in by_status),
    }


def get_decline_reasons(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    rows = _rows(session, q.DECLINE_REASONS, _params(merchant_id, tz, query))
    total = sum(int(r["declined_count"]) for r in rows)
    reasons = [
        {
            "decline_reason": r["decline_reason"],
            "declined_count": int(r["declined_count"]),
            "share_of_declines": rate_float(safe_rate(int(r["declined_count"]), total)),
        }
        for r in rows
    ]
    return {"filters": _filters_echo(query), "total_declined": total, "reasons": reasons}


def get_decline_rate(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    rows = _rows(session, q.DECLINE_COUNTS_BY_NETWORK, _params(merchant_id, tz, query))
    by_network = []
    approved_total = 0
    declined_total = 0
    for r in rows:
        approved = int(r["approved_count"])
        declined = int(r["declined_count"])
        approved_total += approved
        declined_total += declined
        by_network.append(
            {
                "card_network": r["card_network"],
                "transaction_count": approved + declined,
                "declined_count": declined,
                "decline_rate": rate_float(safe_rate(declined, approved + declined)),
            }
        )
    attempts = approved_total + declined_total
    result: dict[str, Any] = {
        "filters": _filters_echo(query),
        "transaction_count": attempts,
        "declined_count": declined_total,
        "decline_rate": rate_float(safe_rate(declined_total, attempts)),
    }
    # The per-network breakdown answers "by card network" questions. It is omitted when the caller
    # already filtered to one network, because it would just repeat the total.
    if query.card_network is None:
        result["by_card_network"] = by_network
    return result


def get_settlement_volume(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    # Settlements are keyed by merchant-local calendar date, so no timezone conversion is needed.
    rows = _rows(
        session,
        q.SETTLEMENT_VOLUME_BY_CURRENCY,
        {
            "merchant_id": merchant_id,
            "start_date": query.start,
            "end_date": query.end,
            "currency": query.currency,
        },
    )
    by_currency = [
        {
            "currency": r["currency"],
            "settlement_count": int(r["settlement_count"]),
            "settled_transaction_count": int(r["settled_transaction_count"]),
            "settled_volume": money_str(Decimal(r["settled_volume"])),
        }
        for r in rows
    ]
    return {"filters": _filters_echo(query), "by_currency": by_currency}


def get_chargeback_rate(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    params = _params(merchant_id, tz, query)
    approved = _scalar_int(session, q.APPROVED_COUNT, params, "approved_count")
    chargebacks = _scalar_int(session, q.CHARGEBACKS_FOR_APPROVED_COHORT, params, "chargeback_count")
    return {
        "filters": _filters_echo(query),
        "approved_transaction_count": approved,
        "chargeback_count": chargebacks,
        "chargeback_rate": rate_float(safe_rate(chargebacks, approved)),
        "cohort_note": "Chargebacks are matched to the transaction date of the original approval.",
    }


def get_card_type_performance(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    rows = _rows(session, q.CARD_TYPE_PERFORMANCE, _params(merchant_id, tz, query))
    buckets = []
    for r in rows:
        approved = int(r["approved_count"])
        declined = int(r["declined_count"])
        buckets.append(
            {
                "card_type": r["card_type"],
                "currency": r["currency"],
                "approved_count": approved,
                "declined_count": declined,
                "decline_rate": rate_float(safe_rate(declined, approved + declined)),
                "approved_volume": money_str(Decimal(r["approved_volume"])),
            }
        )
    return {"filters": _filters_echo(query), "by_card_type_and_currency": buckets}


def get_transaction_volume_by_region(
    session: Session, merchant_id: str, query: AnalyticsQuery
) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    rows = _rows(session, q.VOLUME_BY_REGION, _params(merchant_id, tz, query))
    return {
        "filters": _filters_echo(query),
        "by_region_and_currency": [
            {
                "region": r["region"],
                "currency": r["currency"],
                "approved_count": int(r["approved_count"]),
                "approved_volume": money_str(Decimal(r["approved_volume"])),
            }
            for r in rows
        ],
    }


def get_fraud_indicators(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    params = _params(merchant_id, tz, query)
    totals = session.execute(text(q.TOTAL_TRANSACTIONS), params).mappings().one()
    total = int(totals["transaction_count"])
    flagged = int(totals["flagged_count"])
    by_day = _rows(session, q.FRAUD_INDICATORS_BY_DAY, params)
    return {
        "filters": _filters_echo(query),
        "note": "Risk indicators from scoring rules. These are not confirmed fraud.",
        "transaction_count": total,
        "flagged_count": flagged,
        "flagged_rate": rate_float(safe_rate(flagged, total)),
        "by_day_and_reason": [
            {
                "local_day": r["local_day"].isoformat(),
                "risk_reason": r["risk_reason"],
                "flagged_count": int(r["flagged_count"]),
            }
            for r in by_day
        ],
    }


# Dispatch table: the ONLY way orchestration reaches analytics. Keys are registered tool names.
ANALYTICS_FUNCTIONS: dict[str, Callable[[Session, str, AnalyticsQuery], dict[str, Any]]] = {
    "get_transaction_volume": get_transaction_volume,
    "get_transaction_count": get_transaction_count,
    "get_decline_reasons": get_decline_reasons,
    "get_decline_rate": get_decline_rate,
    "get_settlement_volume": get_settlement_volume,
    "get_chargeback_rate": get_chargeback_rate,
    "get_card_type_performance": get_card_type_performance,
    "get_transaction_volume_by_region": get_transaction_volume_by_region,
    "get_fraud_indicators": get_fraud_indicators,
}


def run_analytics(
    session: Session, tool_name: str, merchant_id: str, query: AnalyticsQuery
) -> dict[str, Any]:
    """Execute a registered analytics function. Raises KeyError for unknown names."""
    function = ANALYTICS_FUNCTIONS[tool_name]
    result = function(session, merchant_id, query)
    result["metric_definition"] = definition_as_dict(tool_name)
    return result
