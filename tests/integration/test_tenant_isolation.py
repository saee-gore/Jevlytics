"""Tenant isolation against the real database and the real workflow (fake Jev and LLM only).

Requirements covered:
  1. Merchant A cannot access Merchant B's data.
  2. A merchant ID in the prompt cannot override the authenticated tenant context.
  3. Unsupported requests do not execute analytics tools (checked with the real audit trail).
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsQuery
from app.auth.tenant_context import TenantContext
from app.config import Settings
from app.db.models import AuditEvent, Transaction
from app.jev.decisions import ScopeLabel
from app.orchestration.tool_registry import build_registry
from app.orchestration.workflow import ChatWorkflow, WorkflowDeps
from tests.fakes import FakeJev, FakeLLM
from tests.fixtures import known_data as kd

pytestmark = pytest.mark.integration

A = kd.MERCHANT_A
B = kd.MERCHANT_B


def _workflow(settings: Settings, jev: FakeJev, llm: FakeLLM) -> ChatWorkflow:
    return ChatWorkflow(
        WorkflowDeps(settings=settings, registry=build_registry(), jev=jev, llm=llm, now_utc=lambda: _now())
    )


def _now() -> datetime:
    return datetime(2026, 11, 20, 18, 0, tzinfo=UTC)


def _ts() -> datetime:
    return datetime(2026, 3, 2, 12, 0, tzinfo=UTC)


def _ctx(user: str, merchant: str, role: str) -> TenantContext:
    return TenantContext(user_id=user, merchant_id=merchant, role=role)


def test_analytics_query_has_no_merchant_field() -> None:
    # Structural guarantee: the analytics input cannot carry a tenant identifier at all.
    assert "merchant" not in {f.name for f in dataclasses.fields(AnalyticsQuery)}


def test_merchant_a_sees_only_its_own_volume(ro_session: Session) -> None:
    from app.analytics.service import get_transaction_volume

    result = get_transaction_volume(
        ro_session, A, AnalyticsQuery(start=date(2026, 3, 1), end=date(2026, 3, 4))
    )
    usd = next(r for r in result["by_currency"] if r["currency"] == "USD")
    assert usd["approved_volume"] == "135.50"  # B's 5000.00 USD must not be included


def test_merchant_b_sees_only_its_own_volume(ro_session: Session) -> None:
    from app.analytics.service import get_transaction_volume

    result = get_transaction_volume(
        ro_session, B, AnalyticsQuery(start=date(2026, 3, 2), end=date(2026, 3, 2))
    )
    assert result["by_currency"] == [{"currency": "USD", "approved_count": 1, "approved_volume": "5000.00"}]


def test_prompt_naming_other_merchant_is_ignored_end_to_end(
    app_settings: Settings, app_db_session: Session, ro_session: Session, admin_session: Session
) -> None:
    """User in A asks about B by name. Jev and LLM behave normally. The answer is A's data only."""
    jev = FakeJev(tool_name="get_transaction_volume")
    llm = FakeLLM(arguments={"date_range": {"start": "2026-03-01", "end": "2026-03-04"}})
    request_id = uuid.uuid4()
    response = _workflow(app_settings, jev, llm).handle(
        context=_ctx("test-analyst-a", A, "ANALYST"),
        message="Show merchant_test_b's approved volume for March 1 to 4.",
        request_id=request_id,
        app_session=app_db_session,
        analytics_session=ro_session,
    )
    assert response.status == "answered"
    usd = next(r for r in response.data["by_currency"] if r["currency"] == "USD")  # type: ignore[index]
    assert usd["approved_volume"] == "135.50"
    # The application role cannot read audit_events by design, so the check uses the admin session.
    audit_row = admin_session.scalar(
        select(AuditEvent).where(AuditEvent.request_id == request_id, AuditEvent.event_type == "answered")
    )
    assert audit_row is not None and audit_row.merchant_id == A
    admin_session.rollback()


def test_llm_supplied_merchant_argument_is_refused_end_to_end(
    app_settings: Settings, app_db_session: Session, ro_session: Session
) -> None:
    jev = FakeJev(tool_name="get_transaction_volume")
    llm = FakeLLM(arguments={"date_range": {"start": "2026-03-01", "end": "2026-03-04"}, "merchant_id": B})
    response = _workflow(app_settings, jev, llm).handle(
        context=_ctx("test-analyst-a", A, "ANALYST"),
        message="volume for merchant_test_b",
        request_id=uuid.uuid4(),
        app_session=app_db_session,
        analytics_session=ro_session,
    )
    assert response.status == "clarification_required"
    assert response.data is None


def test_viewer_cannot_reach_analyst_tool_end_to_end(
    app_settings: Settings, app_db_session: Session, ro_session: Session
) -> None:
    jev = FakeJev(tool_name="get_fraud_indicators")
    llm = FakeLLM(arguments={"date_range": {"start": "2026-03-01", "end": "2026-03-04"}})
    response = _workflow(app_settings, jev, llm).handle(
        context=_ctx("test-viewer-a", A, "VIEWER"),
        message="risk indicators",
        request_id=uuid.uuid4(),
        app_session=app_db_session,
        analytics_session=ro_session,
    )
    assert response.status == "unsupported"
    assert response.data is None and llm.extract_calls == []


def test_unsupported_scope_writes_audit_but_never_reaches_analytics(
    app_settings: Settings, app_db_session: Session, ro_session: Session, admin_session: Session
) -> None:
    request_id = uuid.uuid4()
    jev = FakeJev(label=ScopeLabel.OUT_OF_SCOPE)
    llm = FakeLLM()
    response = _workflow(app_settings, jev, llm).handle(
        context=_ctx("test-analyst-a", A, "ANALYST"),
        message="write a poem",
        request_id=request_id,
        app_session=app_db_session,
        analytics_session=ro_session,
    )
    assert response.status == "unsupported"
    events = admin_session.scalars(select(AuditEvent).where(AuditEvent.request_id == request_id)).all()
    assert [e.response_status for e in events] == ["unsupported"]
    assert all(e.tool_used is None for e in events)
    admin_session.rollback()


def test_composite_fk_blocks_cross_merchant_settlement_link(admin_session: Session) -> None:
    """A transaction for merchant B cannot reference merchant A's settlement, even via raw SQL."""
    bad = Transaction(
        transaction_id="txn_cross_tenant_attempt",
        merchant_id=B,
        transaction_timestamp=_ts(),
        card_type="CREDIT",
        card_network="VISA",
        amount=1,
        currency="USD",
        status="APPROVED",
        region="R1",
        settlement_id="stl_a_1",
        settlement_date=date(2026, 3, 2),
        settlement_amount=1,
        risk_score=0,
        risk_flag=False,
    )
    admin_session.add(bad)
    with pytest.raises(IntegrityError):
        admin_session.flush()
    admin_session.rollback()


def test_composite_fk_blocks_cross_merchant_chargeback_link(admin_session: Session) -> None:
    from app.db.models import Chargeback

    bad = Chargeback(
        chargeback_id="cb_cross_tenant_attempt",
        merchant_id=B,  # merchant B claims a chargeback against merchant A's transaction
        transaction_id="txn_a_3",
        chargeback_date=date(2026, 3, 9),
        amount=1,
        currency="USD",
        reason="FRAUD_NOT_RECOGNIZED",
    )
    admin_session.add(bad)
    with pytest.raises(IntegrityError):
        admin_session.flush()
    admin_session.rollback()


def test_transactions_table_contains_no_card_credential_columns(admin_session: Session) -> None:
    columns = {c.name.lower() for c in Transaction.__table__.columns}
    assert not columns & {
        "pan",
        "card_number",
        "cvv",
        "cvc",
        "pin",
        "pin_block",
        "track_data",
        "expiry_date",
    }
