"""Transaction list and summary for the Activity page.

EXCEPTION TO THE AGGREGATES-ONLY RULE. The rules in queries.py say no statement selects raw rows.
This module is the documented exception: it returns individual transaction rows, limited to the
columns named in TRANSACTION_LIST. It never selects risk, settlement or chargeback columns, and it
never returns another merchant's rows. Every statement binds the trusted merchant_id from the
verified token, through the same BASE_WHERE filter the analytics layer uses.

Reachable only through app/api/routes_transactions.py, which checks the role (ANALYST for the list)
and the rate limit before calling these functions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.analytics import queries as q
from app.analytics.metrics import money_str, rate_float, safe_rate
from app.analytics.service import (
    AnalyticsQuery,
    _filters_echo,
    _merchant_timezone,
    _params,
    _rows,
    _scalar_int,
)

TRANSACTION_LIST = f"""
SELECT t.transaction_id,
       t.transaction_timestamp,
       t.card_type,
       t.card_network,
       t.amount,
       t.currency,
       t.status,
       t.decline_reason,
       t.region
FROM transactions t
WHERE {q.BASE_WHERE}
ORDER BY t.transaction_timestamp DESC, t.transaction_id DESC
LIMIT :limit OFFSET :offset
"""

TRANSACTION_TOTAL = f"""
SELECT COUNT(*) AS total
FROM transactions t
WHERE {q.BASE_WHERE}
"""

COUNT_BY_NETWORK_AND_STATUS = f"""
SELECT t.card_network AS card_network,
       COUNT(*) FILTER (WHERE t.status = 'APPROVED') AS approved_count,
       COUNT(*) FILTER (WHERE t.status = 'DECLINED') AS declined_count,
       COUNT(*) AS transaction_count
FROM transactions t
WHERE {q.BASE_WHERE}
GROUP BY t.card_network
ORDER BY t.card_network
"""


def list_transactions(
    session: Session,
    merchant_id: str,
    query: AnalyticsQuery,
    *,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    params = {**_params(merchant_id, tz, query), "limit": limit, "offset": offset}
    rows = _rows(session, TRANSACTION_LIST, params)
    total = _scalar_int(session, TRANSACTION_TOTAL, params, "total")
    return {
        "filters": _filters_echo(query),
        "total": total,
        "limit": limit,
        "offset": offset,
        "transactions": [
            {
                "transaction_id": r["transaction_id"],
                "transaction_timestamp": r["transaction_timestamp"].isoformat(),
                "card_type": r["card_type"],
                "card_network": r["card_network"],
                "amount": money_str(Decimal(r["amount"])),
                "currency": r["currency"],
                "status": r["status"],
                "decline_reason": r["decline_reason"],
                "region": r["region"],
            }
            for r in rows
        ],
    }


def transaction_summary(session: Session, merchant_id: str, query: AnalyticsQuery) -> dict[str, Any]:
    tz = _merchant_timezone(session, merchant_id)
    params = _params(merchant_id, tz, query)
    status_rows = _rows(session, q.TRANSACTION_COUNT_BY_STATUS, params)
    network_rows = _rows(session, COUNT_BY_NETWORK_AND_STATUS, params)
    volume_rows = _rows(session, q.TRANSACTION_VOLUME_BY_CURRENCY, params)

    approved = sum(int(r["transaction_count"]) for r in status_rows if r["status"] == "APPROVED")
    declined = sum(int(r["transaction_count"]) for r in status_rows if r["status"] == "DECLINED")
    return {
        "filters": _filters_echo(query),
        "by_status": [
            {"status": r["status"], "transaction_count": int(r["transaction_count"])} for r in status_rows
        ],
        "by_card_network": [
            {
                "card_network": r["card_network"],
                "transaction_count": int(r["transaction_count"]),
                "approved_count": int(r["approved_count"]),
                "declined_count": int(r["declined_count"]),
                "decline_rate": rate_float(
                    safe_rate(int(r["declined_count"]), int(r["approved_count"]) + int(r["declined_count"]))
                ),
            }
            for r in network_rows
        ],
        # Currencies are reported separately and never added together.
        "approved_volume_by_currency": [
            {
                "currency": r["currency"],
                "approved_count": int(r["approved_count"]),
                "approved_volume": money_str(Decimal(r["approved_volume"])),
            }
            for r in volume_rows
        ],
        "decline_rate": rate_float(safe_rate(declined, approved + declined)),
    }
