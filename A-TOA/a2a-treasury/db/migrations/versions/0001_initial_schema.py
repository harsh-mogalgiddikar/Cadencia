"""Initial schema — A2A Treasury Network Phase 1

Revision ID: 0001
Revises: None
Create Date: 2026-02-27

Creates all 13 tables plus Row-Level Security on audit_logs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── enterprises ────────────────────────────────────────────────────
    op.create_table(
        "enterprises",
        sa.Column("enterprise_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("pan", sa.String(10), nullable=True),
        sa.Column("gst", sa.String(15), nullable=True),
        sa.Column("authorized_signatory", sa.String(255), nullable=True),
        sa.Column("primary_bank_account", sa.String(50), nullable=True),
        sa.Column("kyc_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("wallet_address", sa.String(128), nullable=True),
        sa.Column("agent_card_url", sa.String(512), nullable=True),
        sa.Column("agent_card_data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kyc_status IN ('PENDING', 'EMAIL_VERIFIED', 'ACTIVE')", name="ck_enterprises_kyc_status"),
    )

    # ─── users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('admin', 'auditor')", name="ck_users_role"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_users_status"),
    )

    # ─── agent_configs ──────────────────────────────────────────────────
    op.create_table(
        "agent_configs",
        sa.Column("config_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False, unique=True),
        sa.Column("agent_role", sa.String(10), nullable=False),
        sa.Column("intrinsic_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("risk_factor", sa.Numeric(5, 4), nullable=False),
        sa.Column("negotiation_margin", sa.Numeric(5, 4), nullable=False, server_default="0.0800"),
        sa.Column("concession_curve", JSONB, nullable=False),
        sa.Column("budget_ceiling", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_exposure", sa.Numeric(18, 6), nullable=False, server_default="100000.000000"),
        sa.Column("strategy_default", sa.String(50), nullable=False, server_default="balanced"),
        sa.Column("max_rounds", sa.Integer, nullable=False, server_default="8"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="3600"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("agent_role IN ('buyer', 'seller', 'both')", name="ck_agent_configs_role"),
    )

    # ─── treasury_policies ──────────────────────────────────────────────
    op.create_table(
        "treasury_policies",
        sa.Column("policy_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("buffer_threshold", sa.Numeric(5, 4), nullable=True),
        sa.Column("risk_tolerance", sa.String(50), nullable=True),
        sa.Column("yield_strategy", sa.String(50), nullable=False, server_default="none"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ─── wallets ────────────────────────────────────────────────────────
    op.create_table(
        "wallets",
        sa.Column("wallet_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False, unique=True),
        sa.Column("address", sa.String(128), nullable=False),
        sa.Column("usdc_balance", sa.Numeric(18, 6), nullable=False, server_default="0.000000"),
        sa.Column("network_id", sa.String(50), nullable=False, server_default="algorand-testnet"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ─── negotiations ──────────────────────────────────────────────────
    op.create_table(
        "negotiations",
        sa.Column("session_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("buyer_enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("seller_enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="INIT"),
        sa.Column("max_rounds", sa.Integer, nullable=False),
        sa.Column("current_round", sa.Integer, nullable=False, server_default="0"),
        sa.Column("timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=True),
        sa.Column("initiated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("final_agreed_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("milestone_template_id", sa.String(100), nullable=True),
        sa.Column("buyer_consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("seller_consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stall_counter", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_buyer_offer", sa.Numeric(18, 6), nullable=True),
        sa.Column("last_seller_offer", sa.Numeric(18, 6), nullable=True),
        sa.CheckConstraint("buyer_enterprise_id != seller_enterprise_id", name="ck_negotiations_diff_parties"),
        sa.CheckConstraint(
            "status IN ('INIT','BUYER_ANCHOR','SELLER_RESPONSE','ROUND_LOOP',"
            "'AGREED','WALKAWAY','TIMEOUT','ROUND_LIMIT','STALLED','POLICY_BREACH')",
            name="ck_negotiations_status",
        ),
    )

    # ─── offers ─────────────────────────────────────────────────────────
    op.create_table(
        "offers",
        sa.Column("offer_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("negotiations.session_id"), nullable=False),
        sa.Column("agent_role", sa.String(10), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("round", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("strategy_tag", sa.String(50), nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("agent_role IN ('buyer', 'seller')", name="ck_offers_agent_role"),
        sa.CheckConstraint("action IN ('counter', 'accept', 'reject', 'timeout_yield')", name="ck_offers_action"),
    )

    # ─── guardrail_logs ─────────────────────────────────────────────────
    op.create_table(
        "guardrail_logs",
        sa.Column("log_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("negotiations.session_id"), nullable=False),
        sa.Column("round", sa.Integer, nullable=False),
        sa.Column("agent_role", sa.String(10), nullable=False),
        sa.Column("rule_violated", sa.String(100), nullable=False),
        sa.Column("proposed_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("threshold", sa.Numeric(18, 6), nullable=True),
        sa.Column("action_taken", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ─── escrow_contracts ───────────────────────────────────────────────
    op.create_table(
        "escrow_contracts",
        sa.Column("escrow_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("negotiations.session_id"), nullable=False),
        sa.Column("contract_ref", sa.String(256), nullable=True),
        sa.Column("network_id", sa.String(50), nullable=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("milestones", JSONB, nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tx_ref", sa.String(256), nullable=True),
    )

    # ─── settlements ────────────────────────────────────────────────────
    op.create_table(
        "settlements",
        sa.Column("settlement_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("escrow_id", UUID(as_uuid=True), sa.ForeignKey("escrow_contracts.escrow_id"), nullable=False),
        sa.Column("tx_ref", sa.String(256), nullable=True),
        sa.Column("amount_released", sa.Numeric(18, 6), nullable=True),
        sa.Column("milestone_ref", sa.String(100), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ─── compliance_records ─────────────────────────────────────────────
    op.create_table(
        "compliance_records",
        sa.Column("record_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("settlement_id", UUID(as_uuid=True), sa.ForeignKey("settlements.settlement_id"), nullable=False),
        sa.Column("purpose_code", sa.String(20), nullable=False, server_default="P1301"),
        sa.Column("counterparty_country", sa.String(50), nullable=True),
        sa.Column("invoice_ref", sa.String(100), nullable=True),
        sa.Column("fema_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # ─── audit_logs ─────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("log_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("this_hash", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
    )

    # ── Row-Level Security on audit_logs ─────────────────────────────────
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute(
        "DO $$ BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_writer') THEN "
        "    CREATE ROLE audit_writer; "
        "  END IF; "
        "END $$;"
    )
    op.execute("GRANT INSERT ON audit_logs TO audit_writer;")
    op.execute(
        "CREATE POLICY audit_insert_only ON audit_logs "
        "FOR INSERT TO audit_writer "
        "WITH CHECK (true);"
    )

    # ─── fx_quotes ──────────────────────────────────────────────────────
    op.create_table(
        "fx_quotes",
        sa.Column("quote_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enterprise_id", UUID(as_uuid=True), sa.ForeignKey("enterprises.enterprise_id"), nullable=False),
        sa.Column("from_currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("to_currency", sa.String(10), nullable=False, server_default="USDC"),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("spread", sa.Numeric(6, 4), nullable=True),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("fx_quotes")
    op.execute("DROP POLICY IF EXISTS audit_insert_only ON audit_logs;")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY;")
    op.drop_table("audit_logs")
    op.drop_table("compliance_records")
    op.drop_table("settlements")
    op.drop_table("escrow_contracts")
    op.drop_table("guardrail_logs")
    op.drop_table("offers")
    op.drop_table("negotiations")
    op.drop_table("wallets")
    op.drop_table("treasury_policies")
    op.drop_table("agent_configs")
    op.drop_table("users")
    op.drop_table("enterprises")
