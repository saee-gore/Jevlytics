"""ORM models. The Alembic migration in alembic/versions/0001_initial.py mirrors this schema.

Tenant integrity: transactions and chargebacks carry (id, merchant_id) composite foreign keys, so a
row cannot reference a settlement or transaction belonging to a different merchant, even if
application code has a bug.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MONEY = Numeric(14, 2)
CARD_TYPES = ("CREDIT", "DEBIT")
CARD_NETWORKS = ("VISA", "MASTERCARD", "AMEX", "DISCOVER")
TRANSACTION_STATUSES = ("APPROVED", "DECLINED", "PENDING", "REVERSED", "REFUNDED")
ROLES = ("ANALYST", "VIEWER")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(160))
    vertical: Mapped[str] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in_list("role", ROLES), name="ck_users_role"),
        Index("ix_users_merchant", "merchant_id"),
    )

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"))
    role: Mapped[str] = mapped_column(String(16))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("settlement_id", "merchant_id", name="uq_settlements_id_merchant"),
        Index("ix_settlements_merchant_date", "merchant_id", "settlement_date"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_settlements_currency"),
    )

    settlement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"))
    settlement_date: Mapped[dt.date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    gross_amount: Mapped[Decimal] = mapped_column(MONEY)
    transaction_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("transaction_id", "merchant_id", name="uq_transactions_id_merchant"),
        ForeignKeyConstraint(
            ["settlement_id", "merchant_id"],
            ["settlements.settlement_id", "settlements.merchant_id"],
            name="fk_transactions_settlement_same_merchant",
        ),
        CheckConstraint(_in_list("card_type", CARD_TYPES), name="ck_txn_card_type"),
        CheckConstraint(_in_list("card_network", CARD_NETWORKS), name="ck_txn_card_network"),
        CheckConstraint(_in_list("status", TRANSACTION_STATUSES), name="ck_txn_status"),
        CheckConstraint("amount >= 0", name="ck_txn_amount_nonnegative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_txn_currency"),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_txn_risk_score"),
        Index("ix_txn_merchant_ts", "merchant_id", "transaction_timestamp"),
        Index("ix_txn_merchant_status", "merchant_id", "status"),
        Index("ix_txn_merchant_card", "merchant_id", "card_type", "card_network"),
        Index("ix_txn_merchant_region", "merchant_id", "region"),
    )

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"))
    transaction_timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    card_type: Mapped[str] = mapped_column(String(8))
    card_network: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16))
    decline_reason: Mapped[str | None] = mapped_column(String(40))
    region: Mapped[str] = mapped_column(String(32))
    settlement_id: Mapped[str | None] = mapped_column(String(64))
    settlement_date: Mapped[dt.date | None] = mapped_column(Date)
    settlement_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    # Denormalised from chargebacks for convenience; chargebacks.transaction_id is authoritative.
    chargeback_id: Mapped[str | None] = mapped_column(String(64))
    chargeback_date: Mapped[dt.date | None] = mapped_column(Date)
    chargeback_reason: Mapped[str | None] = mapped_column(String(40))
    risk_score: Mapped[int] = mapped_column(SmallInteger)
    risk_flag: Mapped[bool] = mapped_column(Boolean)
    risk_reason: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Chargeback(Base):
    __tablename__ = "chargebacks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["transaction_id", "merchant_id"],
            ["transactions.transaction_id", "transactions.merchant_id"],
            name="fk_chargebacks_transaction_same_merchant",
        ),
        UniqueConstraint("transaction_id", name="uq_chargebacks_transaction"),
        Index("ix_chargebacks_merchant_date", "merchant_id", "chargeback_date"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_chargebacks_currency"),
    )

    chargeback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.merchant_id"))
    transaction_id: Mapped[str] = mapped_column(String(64))
    chargeback_date: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    reason: Mapped[str] = mapped_column(String(40))


class AuditEvent(Base):
    """Structured audit trail. Stores codes and hashes only: never raw prompts or result rows."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_merchant_time", "merchant_id", "occurred_at"),
        Index("ix_audit_request", "request_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    merchant_id: Mapped[str | None] = mapped_column(String(32))
    user_id: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(40))
    jev_scope: Mapped[str | None] = mapped_column(String(40))
    jev_tool: Mapped[str | None] = mapped_column(String(40))
    jev_latency_ms: Mapped[int | None] = mapped_column(Integer)
    policy_outcome: Mapped[str | None] = mapped_column(String(40))
    tool_used: Mapped[str | None] = mapped_column(String(40))
    response_status: Mapped[str] = mapped_column(String(40))
    question_sha256: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict[str, object]] = mapped_column(JSONB, server_default="{}")
