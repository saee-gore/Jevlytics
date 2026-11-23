"""GET /transactions and GET /transactions/summary against the real database.

Requirements covered:
  1. Listing rows needs ANALYST. Viewers are refused; the summary is available to VIEWER.
  2. Each merchant sees only its own rows (the merchant comes from the verified token).
  3. Invalid dates, spans, pages and filters are rejected before any query runs.
  4. Every row listing is written to the audit trail with counts only.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import issue_token
from app.config import Settings
from app.db.models import AuditEvent
from app.main import create_app
from tests.fakes import FakeJev, FakeLLM
from tests.fixtures import known_data as kd

pytestmark = pytest.mark.integration

A = kd.MERCHANT_A
B = kd.MERCHANT_B
NOW = datetime(2026, 11, 20, 18, 0, tzinfo=UTC)
WINDOW = {"start": "2026-01-01", "end": "2026-12-31"}


@pytest.fixture
def client(app_settings: Settings) -> Iterator[TestClient]:
    app = create_app(
        app_settings,
        jev=FakeJev(tool_name="get_transaction_volume"),
        llm=FakeLLM(),
        now_utc=lambda: NOW,
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _auth(settings: Settings, user: str, merchant: str, role: str) -> dict[str, str]:
    token = issue_token(settings=settings, user_id=user, merchant_id=merchant, role=role, ttl_minutes=10)
    return {"Authorization": f"Bearer {token}"}


def test_list_requires_authentication(client: TestClient) -> None:
    assert client.get("/transactions", params=WINDOW).status_code == 401


def test_viewer_cannot_list_rows_but_can_read_summary(client: TestClient, app_settings: Settings) -> None:
    viewer = _auth(app_settings, "test-viewer-a", A, "VIEWER")
    assert client.get("/transactions", params=WINDOW, headers=viewer).status_code == 403
    assert client.get("/transactions/summary", params=WINDOW, headers=viewer).status_code == 200


def test_analyst_list_has_contract_shape_and_no_risk_columns(
    client: TestClient, app_settings: Settings
) -> None:
    analyst = _auth(app_settings, "test-analyst-a", A, "ANALYST")
    response = client.get("/transactions", params={**WINDOW, "limit": 5}, headers=analyst)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"filters", "total", "limit", "offset", "transactions", "request_id"}
    for row in body["transactions"]:
        assert set(row) == {
            "transaction_id",
            "transaction_timestamp",
            "card_type",
            "card_network",
            "amount",
            "currency",
            "status",
            "decline_reason",
            "region",
        }


def test_merchants_never_see_each_others_rows(client: TestClient, app_settings: Settings) -> None:
    a = _auth(app_settings, "test-analyst-a", A, "ANALYST")
    b = _auth(app_settings, "test-analyst-b", B, "ANALYST")
    ids_a = {
        t["transaction_id"]
        for t in client.get("/transactions", params={**WINDOW, "limit": 100}, headers=a).json()[
            "transactions"
        ]
    }
    ids_b = {
        t["transaction_id"]
        for t in client.get("/transactions", params={**WINDOW, "limit": 100}, headers=b).json()[
            "transactions"
        ]
    }
    assert ids_a, "fixture merchant A should have transactions in the window"
    assert ids_b, "fixture merchant B should have transactions in the window"
    assert not (ids_a & ids_b)


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-11-20", "end": "2026-11-01"},  # end before start
        {"start": "2024-01-01", "end": "2026-12-31"},  # longer than 366 days
        {**WINDOW, "status": "DROP"},  # not an allowed status
        {**WINDOW, "limit": 101},  # above the page limit
        {**WINDOW, "offset": -1},  # negative offset
        {**WINDOW, "card_network": "visa; drop"},  # not a plain network code
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, app_settings: Settings, params: dict) -> None:
    analyst = _auth(app_settings, "test-analyst-a", A, "ANALYST")
    assert client.get("/transactions", params=params, headers=analyst).status_code == 422


def test_each_row_listing_is_audited_with_counts_only(
    client: TestClient, app_settings: Settings, admin_session: Session
) -> None:
    analyst = _auth(app_settings, "test-analyst-a", A, "ANALYST")
    response = client.get("/transactions", params={**WINDOW, "limit": 5}, headers=analyst)
    assert response.status_code == 200
    events = (
        admin_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "transactions_listed", AuditEvent.merchant_id == A)
        .order_by(AuditEvent.id.desc())
        .limit(1)
        .all()
    )
    assert events, "the row listing should write an audit event"
    detail = events[0].detail
    assert set(detail) <= {"row_count", "date_span_days"}
    assert detail["row_count"] == len(response.json()["transactions"])
