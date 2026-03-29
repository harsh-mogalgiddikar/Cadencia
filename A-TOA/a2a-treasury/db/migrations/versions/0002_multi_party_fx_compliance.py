"""Phase 3 — Multi-party, FX, Compliance schema changes

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-28

Adds:
  - New columns to negotiations table (FX, compliance, multi-party)
  - multi_party_sessions table
  - Drops and recreates fx_quotes table with new schema
  - Drops and recreates compliance_records table with new schema
  - New indexes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── negotiations: add Phase 3 columns ──────────────────────────────
    op.add_column("negotiations", sa.Column("fx_quote_id", UUID(as_uuid=True), nullable=True))
    op.add_column("negotiations", sa.Column("fx_rate_locked", sa.Numeric(18, 8), nullable=True))
    op.add_column("negotiations", sa.Column("usdc_equivalent", sa.Numeric(15, 6), nullable=True))
    op.add_column("negotiations", sa.Column("compliance_status", sa.String(20), nullable=True))
    op.add_column("negotiations", sa.Column("multi_session_id", UUID(as_uuid=True), nullable=True))

    # ─── Drop and recreate fx_quotes with new schema ────────────────────
    op.drop_table("fx_quotes")
    op.create_table(
        "fx_quotes",
        sa.Column("quote_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("base_currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("quote_currency", sa.String(10), nullable=False, server_default="USDC"),
        sa.Column("mid_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("spread_bps", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("buy_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("sell_rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="fallback"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_fx_quotes_session_id", "fx_quotes", ["session_id"])
    op.create_index("ix_fx_quotes_fetched_at", "fx_quotes", ["fetched_at"])

    # ─── Drop and recreate compliance_records with new schema ──────────
    op.drop_table("compliance_records")
    op.create_table(
        "compliance_records",
        sa.Column("record_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("negotiations.session_id"), nullable=True),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=True),
        sa.Column("purpose_code", sa.String(20), nullable=False, server_default="P0103"),
        sa.Column("purpose_label", sa.String(255), nullable=True),
        sa.Column("transaction_type", sa.String(20), nullable=True),
        sa.Column("inr_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("usdc_amount", sa.Numeric(15, 6), nullable=True),
        sa.Column("usd_equivalent", sa.Numeric(15, 6), nullable=True),
        sa.Column("limit_applicable", sa.Numeric(15, 6), nullable=True),
        sa.Column("limit_utilization_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="COMPLIANT"),
        sa.Column("warnings", JSONB, nullable=True),
        sa.Column("blocking_reasons", JSONB, nullable=True),
        sa.Column("counterparty_country", sa.String(50), nullable=True),
        sa.Column("invoice_ref", sa.String(100), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_compliance_records_enterprise_id", "compliance_records", ["enterprise_id"])

    # ─── multi_party_sessions ───────────────────────────────────────────
    op.create_table(
        "multi_party_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("buyer_enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("seller_ids", JSONB, nullable=False),
        sa.Column("child_session_ids", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("best_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("best_offer_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_multi_party_buyer", "multi_party_sessions", ["buyer_enterprise_id"])


def downgrade() -> None:
    op.drop_table("multi_party_sessions")

    # Restore old compliance_records schema
    op.drop_table("compliance_records")
    op.create_table(
        "compliance_records",
        sa.Column("record_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("settlement_id", UUID(as_uuid=True), sa.ForeignKey("settlements.settlement_id"), nullable=False),
        sa.Column("purpose_code", sa.String(20), nullable=False, server_default="P1301"),
        sa.Column("counterparty_country", sa.String(50), nullable=True),
        sa.Column("invoice_ref", sa.String(100), nullable=True),
        sa.Column("fema_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Restore old fx_quotes schema
    op.drop_table("fx_quotes")
    op.create_table(
        "fx_quotes",
        sa.Column("quote_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("from_currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("to_currency", sa.String(10), nullable=False, server_default="USDC"),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("spread", sa.Numeric(6, 4), nullable=True),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.drop_column("negotiations", "multi_session_id")
    op.drop_column("negotiations", "compliance_status")
    op.drop_column("negotiations", "usdc_equivalent")
    op.drop_column("negotiations", "fx_rate_locked")
    op.drop_column("negotiations", "fx_quote_id")
