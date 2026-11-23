"""Initial schema: merchants, users, settlements, transactions, chargebacks, audit_events.

Revision ID: 0001_initial
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("merchant_id", sa.String(32), primary_key=True),
        sa.Column("legal_name", sa.String(160), nullable=False),
        sa.Column("vertical", sa.String(64), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("merchant_id", sa.String(32), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('ANALYST', 'VIEWER')", name="ck_users_role"),
    )
    op.create_index("ix_users_merchant", "users", ["merchant_id"])

    op.create_table(
        "settlements",
        sa.Column("settlement_id", sa.String(64), primary_key=True),
        sa.Column("merchant_id", sa.String(32), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("gross_amount", MONEY, nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("settlement_id", "merchant_id", name="uq_settlements_id_merchant"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_settlements_currency"),
    )
    op.create_index("ix_settlements_merchant_date", "settlements", ["merchant_id", "settlement_date"])

    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.String(64), primary_key=True),
        sa.Column("merchant_id", sa.String(32), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("transaction_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("card_type", sa.String(8), nullable=False),
        sa.Column("card_network", sa.String(16), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("decline_reason", sa.String(40), nullable=True),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("settlement_id", sa.String(64), nullable=True),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("settlement_amount", MONEY, nullable=True),
        sa.Column("chargeback_id", sa.String(64), nullable=True),
        sa.Column("chargeback_date", sa.Date(), nullable=True),
        sa.Column("chargeback_reason", sa.String(40), nullable=True),
        sa.Column("risk_score", sa.SmallInteger(), nullable=False),
        sa.Column("risk_flag", sa.Boolean(), nullable=False),
        sa.Column("risk_reason", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("transaction_id", "merchant_id", name="uq_transactions_id_merchant"),
        sa.ForeignKeyConstraint(
            ["settlement_id", "merchant_id"],
            ["settlements.settlement_id", "settlements.merchant_id"],
            name="fk_transactions_settlement_same_merchant",
        ),
        sa.CheckConstraint("card_type IN ('CREDIT', 'DEBIT')", name="ck_txn_card_type"),
        sa.CheckConstraint(
            "card_network IN ('VISA', 'MASTERCARD', 'AMEX', 'DISCOVER')", name="ck_txn_card_network"
        ),
        sa.CheckConstraint(
            "status IN ('APPROVED', 'DECLINED', 'PENDING', 'REVERSED', 'REFUNDED')",
            name="ck_txn_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_txn_amount_nonnegative"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_txn_currency"),
        sa.CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_txn_risk_score"),
    )
    op.create_index("ix_txn_merchant_ts", "transactions", ["merchant_id", "transaction_timestamp"])
    op.create_index("ix_txn_merchant_status", "transactions", ["merchant_id", "status"])
    op.create_index("ix_txn_merchant_card", "transactions", ["merchant_id", "card_type", "card_network"])
    op.create_index("ix_txn_merchant_region", "transactions", ["merchant_id", "region"])

    op.create_table(
        "chargebacks",
        sa.Column("chargeback_id", sa.String(64), primary_key=True),
        sa.Column("merchant_id", sa.String(32), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("transaction_id", sa.String(64), nullable=False),
        sa.Column("chargeback_date", sa.Date(), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.UniqueConstraint("transaction_id", name="uq_chargebacks_transaction"),
        sa.ForeignKeyConstraint(
            ["transaction_id", "merchant_id"],
            ["transactions.transaction_id", "transactions.merchant_id"],
            name="fk_chargebacks_transaction_same_merchant",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_chargebacks_currency"),
    )
    op.create_index("ix_chargebacks_merchant_date", "chargebacks", ["merchant_id", "chargeback_date"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("merchant_id", sa.String(32), nullable=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("jev_scope", sa.String(40), nullable=True),
        sa.Column("jev_tool", sa.String(40), nullable=True),
        sa.Column("jev_latency_ms", sa.Integer(), nullable=True),
        sa.Column("policy_outcome", sa.String(40), nullable=True),
        sa.Column("tool_used", sa.String(40), nullable=True),
        sa.Column("response_status", sa.String(40), nullable=False),
        sa.Column("question_sha256", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(), server_default="{}", nullable=False),
    )
    op.create_index("ix_audit_merchant_time", "audit_events", ["merchant_id", "occurred_at"])
    op.create_index("ix_audit_request", "audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("chargebacks")
    op.drop_table("transactions")
    op.drop_table("settlements")
    op.drop_index("ix_users_merchant", table_name="users")
    op.drop_table("users")
    op.drop_table("merchants")
