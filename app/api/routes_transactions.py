"""GET /transactions and GET /transactions/summary, used by the Activity page.

Both routes are merchant-scoped: the merchant comes only from the verified token. Listing rows
needs the ANALYST role; the summary needs VIEWER, like the other aggregate endpoints. Every row
list request is written to the audit log (hashed filters and counts only).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsQuery, MerchantNotFoundError
from app.analytics.transactions import list_transactions, transaction_summary
from app.api.dependencies import enforce_rate_limit, get_analytics_session, get_app_session
from app.auth.tenant_context import TenantContext
from app.orchestration import audit
from app.orchestration.tool_registry import ROLE_RANK

router = APIRouter()

MAX_SPAN_DAYS = 366
MAX_PAGE_SIZE = 100
MAX_OFFSET = 100_000
StatusFilter = Literal["APPROVED", "DECLINED", "PENDING", "REFUNDED", "REVERSED"]
CardTypeFilter = Literal["CREDIT", "DEBIT"]


class TransactionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: str
    transaction_timestamp: str
    card_type: str
    card_network: str
    amount: str
    currency: str
    status: str
    decline_reason: str | None
    region: str


class TransactionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: dict[str, Any]
    total: int
    limit: int
    offset: int
    transactions: list[TransactionItem]
    request_id: str


class StatusCount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    transaction_count: int


class NetworkBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_network: str
    transaction_count: int
    approved_count: int
    declined_count: int
    decline_rate: float | None


class CurrencyVolume(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: str
    approved_count: int
    approved_volume: str


class TransactionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: dict[str, Any]
    by_status: list[StatusCount]
    by_card_network: list[NetworkBreakdown]
    approved_volume_by_currency: list[CurrencyVolume]
    decline_rate: float | None
    request_id: str


def _check_window(start: date, end: date) -> int:
    if end < start:
        raise HTTPException(status_code=422, detail="end must not be before start.")
    span = (end - start).days + 1
    if span > MAX_SPAN_DAYS:
        raise HTTPException(status_code=422, detail=f"The date range may not exceed {MAX_SPAN_DAYS} days.")
    return span


def _digest(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


@router.get("/transactions", response_model=TransactionListResponse)
def get_transactions(
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    status_filter: Annotated[StatusFilter | None, Query(alias="status")] = None,
    card_type: Annotated[CardTypeFilter | None, Query()] = None,
    card_network: Annotated[str | None, Query(min_length=1, max_length=16, pattern=r"^[A-Z_]+$")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
    tenant: TenantContext = Depends(enforce_rate_limit),  # noqa: B008
    app_session: Session = Depends(get_app_session),  # noqa: B008
    analytics_session: Session = Depends(get_analytics_session),  # noqa: B008
) -> TransactionListResponse:
    if ROLE_RANK.get(tenant.role, 0) < ROLE_RANK["ANALYST"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Your role cannot list transactions."
        )
    span = _check_window(start, end)
    query = AnalyticsQuery(
        start=start, end=end, status=status_filter, card_type=card_type, card_network=card_network
    )
    request_id = uuid.uuid4()
    try:
        payload = list_transactions(analytics_session, tenant.merchant_id, query, limit=limit, offset=offset)
    except MerchantNotFoundError:
        raise HTTPException(status_code=404, detail="Merchant not found.") from None

    audit.record_event(
        app_session,
        request_id=request_id,
        event_type="transactions_listed",
        response_status="answered",
        question=_digest(start, end, status_filter, card_type, card_network, limit, offset),
        merchant_id=tenant.merchant_id,
        user_id=tenant.user_id,
        detail={"row_count": len(payload["transactions"]), "date_span_days": span},
    )
    payload["request_id"] = str(request_id)
    return TransactionListResponse(**payload)


@router.get("/transactions/summary", response_model=TransactionSummaryResponse)
def get_transaction_summary(
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    tenant: TenantContext = Depends(enforce_rate_limit),  # noqa: B008
    analytics_session: Session = Depends(get_analytics_session),  # noqa: B008
) -> TransactionSummaryResponse:
    _check_window(start, end)
    query = AnalyticsQuery(start=start, end=end)
    try:
        payload = transaction_summary(analytics_session, tenant.merchant_id, query)
    except MerchantNotFoundError:
        raise HTTPException(status_code=404, detail="Merchant not found.") from None
    payload["request_id"] = str(uuid.uuid4())
    return TransactionSummaryResponse(**payload)
