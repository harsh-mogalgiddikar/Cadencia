"""
db/models.py — SQLAlchemy 2.x async ORM models for A2A Treasury Network.

All tables use UUID v4 primary keys (native PostgreSQL UUID type).
All timestamps are TIMESTAMP WITH TIME ZONE stored as UTC.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ─── helpers ────────────────────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── enterprises ────────────────────────────────────────────────────────────────
class Enterprise(Base):
    __tablename__ = "enterprises"

    enterprise_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_name = Column(String(255), nullable=False)
    pan = Column(String(10), nullable=True)
    gst = Column(String(15), nullable=True)
    authorized_signatory = Column(String(255), nullable=True)
    primary_bank_account = Column(String(50), nullable=True)
    kyc_status = Column(
        String(20), nullable=False, default="PENDING",
    )
    wallet_address = Column(String(128), nullable=True)
    agent_card_url = Column(String(512), nullable=True)
    agent_card_data = Column(JSONB, nullable=True)
    webhook_url = Column(String(512), nullable=True)
    webhook_secret = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=_utcnow)

    # relationships
    users = relationship("User", back_populates="enterprise")
    agent_config = relationship("AgentConfig", back_populates="enterprise", uselist=False)
    wallet = relationship("Wallet", back_populates="enterprise", uselist=False)
    treasury_policies = relationship("TreasuryPolicy", back_populates="enterprise")

    __table_args__ = (
        CheckConstraint(
            "kyc_status IN ('PENDING', 'EMAIL_VERIFIED', 'ACTIVE')",
            name="ck_enterprises_kyc_status",
        ),
    )


# ─── users ──────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    user_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    enterprise = relationship("Enterprise", back_populates="users")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'auditor')", name="ck_users_role"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_users_status"),
    )


# ─── subscription_plans (B2B SaaS) ───────────────────────────────────────────────
class SubscriptionPlan(Base):
    """
    Catalog of subscription plans for enterprises (multi-tenant SaaS).
    """

    __tablename__ = "subscription_plans"

    plan_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    monthly_price_usd = Column(Numeric(10, 2), nullable=False, default=0.0)
    max_sessions_per_month = Column(Integer, nullable=True)
    max_concurrent_sessions = Column(Integer, nullable=True)
    max_enterprises_per_group = Column(Integer, nullable=True)
    features = Column(JSONB, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ─── subscriptions (enterprise ↔ plan) ──────────────────────────────────────────
class Subscription(Base):
    """
    Active subscription for an enterprise.
    """

    __tablename__ = "subscriptions"

    subscription_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("enterprises.enterprise_id"),
        nullable=False,
    )
    plan_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscription_plans.plan_id"),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="active")
    current_period_start = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    seat_count = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','past_due','canceled','incomplete')",
            name="ck_subscriptions_status",
        ),
    )


# ─── api_keys (per-enterprise access tokens) ─────────────────────────────────────
class ApiKey(Base):
    """
    Long-lived API keys for B2B integrations (hashed at rest).
    """

    __tablename__ = "api_keys"

    key_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("enterprises.enterprise_id"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(12), nullable=False)  # first few chars for identification
    hashed_key = Column(String(128), nullable=False)
    scopes = Column(JSONB, nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    revoked = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("enterprise_id", "name", name="uq_api_keys_enterprise_name"),
    )


# ─── agent_configs ──────────────────────────────────────────────────────────────
class AgentConfig(Base):
    __tablename__ = "agent_configs"

    config_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"),
        nullable=False, unique=True,
    )
    agent_role = Column(String(10), nullable=False)
    intrinsic_value = Column(Numeric(18, 6), nullable=False)
    risk_factor = Column(Numeric(5, 4), nullable=False)
    negotiation_margin = Column(Numeric(5, 4), nullable=False, default=0.08)
    concession_curve = Column(JSONB, nullable=False)
    budget_ceiling = Column(Numeric(18, 6), nullable=True)
    max_exposure = Column(Numeric(18, 6), nullable=False, default=100000.0)
    strategy_default = Column(String(50), nullable=False, default="balanced")
    max_rounds = Column(Integer, nullable=False, default=8)
    timeout_seconds = Column(Integer, nullable=False, default=3600)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=_utcnow)

    enterprise = relationship("Enterprise", back_populates="agent_config")

    __table_args__ = (
        CheckConstraint(
            "agent_role IN ('buyer', 'seller', 'both')",
            name="ck_agent_configs_role",
        ),
    )


# ─── treasury_policies ─────────────────────────────────────────────────────────
class TreasuryPolicy(Base):
    __tablename__ = "treasury_policies"

    policy_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    buffer_threshold = Column(Numeric(5, 4), nullable=True)
    risk_tolerance = Column(String(50), nullable=True)
    yield_strategy = Column(String(50), nullable=False, default="none")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    enterprise = relationship("Enterprise", back_populates="treasury_policies")


# ─── wallets ────────────────────────────────────────────────────────────────────
class Wallet(Base):
    __tablename__ = "wallets"

    wallet_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"),
        nullable=False, unique=True,
    )
    address = Column(String(128), nullable=False)
    usdc_balance = Column(Numeric(18, 6), nullable=False, default=0.0)
    network_id = Column(String(50), nullable=False, default="algorand-testnet")
    updated_at = Column(DateTime(timezone=True), default=_utcnow)

    enterprise = relationship("Enterprise", back_populates="wallet")


# ─── negotiations ──────────────────────────────────────────────────────────────
class Negotiation(Base):
    __tablename__ = "negotiations"

    session_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    seller_enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    status = Column(String(30), nullable=False, default="INIT")
    max_rounds = Column(Integer, nullable=False)
    current_round = Column(Integer, nullable=False, default=0)
    timeout_at = Column(DateTime(timezone=True), nullable=False)
    outcome = Column(String(30), nullable=True)
    initiated_at = Column(DateTime(timezone=True), default=_utcnow)
    final_agreed_value = Column(Numeric(18, 6), nullable=True)
    milestone_template_id = Column(String(100), nullable=True)
    buyer_consecutive_failures = Column(Integer, nullable=False, default=0)
    seller_consecutive_failures = Column(Integer, nullable=False, default=0)
    stall_counter = Column(Integer, nullable=False, default=0)
    last_buyer_offer = Column(Numeric(18, 6), nullable=True)
    last_seller_offer = Column(Numeric(18, 6), nullable=True)
    # Phase 3 columns
    fx_quote_id = Column(PG_UUID(as_uuid=True), nullable=True)
    fx_rate_locked = Column(Numeric(18, 8), nullable=True)
    usdc_equivalent = Column(Numeric(15, 6), nullable=True)
    compliance_status = Column(String(20), nullable=True)
    multi_session_id = Column(PG_UUID(as_uuid=True), nullable=True)
    # Phase 5 delivery columns
    delivery_status = Column(String(32), nullable=True)
    delivery_tx_id = Column(String(128), nullable=True)
    # Phase 3 ACF — Merkle verification + on-chain anchor
    merkle_root = Column(String(64), nullable=True)
    anchor_tx_id = Column(String(128), nullable=True)

    # relationships
    offers = relationship("Offer", back_populates="negotiation")
    guardrail_logs = relationship("GuardrailLog", back_populates="negotiation")

    __table_args__ = (
        CheckConstraint(
            "buyer_enterprise_id != seller_enterprise_id",
            name="ck_negotiations_diff_parties",
        ),
        CheckConstraint(
            "status IN ('INIT','BUYER_ANCHOR','SELLER_RESPONSE','ROUND_LOOP',"
            "'AGREED','WALKAWAY','TIMEOUT','ROUND_LIMIT','STALLED','POLICY_BREACH')",
            name="ck_negotiations_status",
        ),
    )


# ─── offers ─────────────────────────────────────────────────────────────────────
class Offer(Base):
    __tablename__ = "offers"

    offer_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.session_id"), nullable=False,
    )
    agent_role = Column(String(10), nullable=False)
    value = Column(Numeric(18, 6), nullable=True)
    action = Column(String(20), nullable=False)
    round = Column(Integer, nullable=False)
    confidence = Column(Numeric(4, 3), nullable=True)
    strategy_tag = Column(String(50), nullable=True)
    rationale = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)

    negotiation = relationship("Negotiation", back_populates="offers")

    __table_args__ = (
        CheckConstraint(
            "agent_role IN ('buyer', 'seller')", name="ck_offers_agent_role",
        ),
        CheckConstraint(
            "action IN ('counter', 'accept', 'reject', 'timeout_yield')",
            name="ck_offers_action",
        ),
    )


# ─── guardrail_logs ─────────────────────────────────────────────────────────────
class GuardrailLog(Base):
    __tablename__ = "guardrail_logs"

    log_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.session_id"), nullable=False,
    )
    round = Column(Integer, nullable=False)
    agent_role = Column(String(10), nullable=False)
    rule_violated = Column(String(100), nullable=False)
    proposed_value = Column(Numeric(18, 6), nullable=True)
    threshold = Column(Numeric(18, 6), nullable=True)
    action_taken = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)

    negotiation = relationship("Negotiation", back_populates="guardrail_logs")


# ─── escrow_contracts ───────────────────────────────────────────────────────────
class EscrowContract(Base):
    __tablename__ = "escrow_contracts"

    escrow_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.session_id"), nullable=False,
    )
    contract_ref = Column(String(256), nullable=True)
    network_id = Column(String(50), nullable=True)
    amount = Column(Numeric(18, 6), nullable=True)
    status = Column(String(30), nullable=True)
    milestones = Column(JSONB, nullable=True)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    tx_ref = Column(String(256), nullable=True)
    # Smart contract app_id on Algorand (replaces multisig contract_ref)
    app_id = Column(Integer, nullable=True)
    # Phase 4 settlement columns
    fund_tx_id = Column(String(128), nullable=True)
    funded_at = Column(DateTime(timezone=True), nullable=True)
    release_tx_id = Column(String(128), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    refund_tx_id = Column(String(128), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    refund_reason = Column(Text, nullable=True)
    # Phase 1: Algorand deployment transaction ID
    deploy_txid = Column(String(128), nullable=True)


# ─── settlements ────────────────────────────────────────────────────────────────
class Settlement(Base):
    __tablename__ = "settlements"

    settlement_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    escrow_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("escrow_contracts.escrow_id"), nullable=False,
    )
    tx_ref = Column(String(256), nullable=True)
    amount_released = Column(Numeric(18, 6), nullable=True)
    milestone_ref = Column(String(100), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)


# ─── compliance_records ─────────────────────────────────────────────────────────
class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    record_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.session_id"), nullable=True,
    )
    enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=True,
    )
    purpose_code = Column(String(20), nullable=False, default="P0103")
    purpose_label = Column(String(255), nullable=True)
    transaction_type = Column(String(20), nullable=True)  # ODI, FDI, DOMESTIC
    inr_amount = Column(Numeric(18, 6), nullable=True)
    usdc_amount = Column(Numeric(15, 6), nullable=True)
    usd_equivalent = Column(Numeric(15, 6), nullable=True)
    limit_applicable = Column(Numeric(15, 6), nullable=True)
    limit_utilization_pct = Column(Numeric(8, 4), nullable=True)
    status = Column(String(20), nullable=False, default="COMPLIANT")
    warnings = Column(JSONB, nullable=True)
    blocking_reasons = Column(JSONB, nullable=True)
    counterparty_country = Column(String(50), nullable=True)
    invoice_ref = Column(String(100), nullable=True)
    checked_at = Column(DateTime(timezone=True), default=_utcnow)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ─── audit_logs ─────────────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(PG_UUID(as_uuid=True), nullable=False)
    action = Column(String(200), nullable=False)
    actor_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)
    prev_hash = Column(String(64), nullable=False)
    this_hash = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=True)


# ─── fx_quotes ──────────────────────────────────────────────────────────────────
class FxQuote(Base):
    __tablename__ = "fx_quotes"

    quote_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(PG_UUID(as_uuid=True), nullable=True)
    base_currency = Column(String(10), nullable=False, default="INR")
    quote_currency = Column(String(10), nullable=False, default="USDC")
    mid_rate = Column(Numeric(18, 8), nullable=False)
    spread_bps = Column(Integer, nullable=False, default=25)
    buy_rate = Column(Numeric(18, 8), nullable=False)
    sell_rate = Column(Numeric(18, 8), nullable=False)
    source = Column(String(50), nullable=False, default="fallback")
    fetched_at = Column(DateTime(timezone=True), default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ─── multi_party_sessions ──────────────────────────────────────────────────────
class MultiPartySession(Base):
    __tablename__ = "multi_party_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    seller_ids = Column(JSONB, nullable=False)
    child_session_ids = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="ACTIVE")
    best_session_id = Column(PG_UUID(as_uuid=True), nullable=True)
    best_offer_value = Column(Numeric(15, 2), nullable=True)
    timeout_seconds = Column(Integer, nullable=False, default=3600)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    concluded_at = Column(DateTime(timezone=True), nullable=True)


# ─── deliveries (Phase 5 — x402 payment records) ───────────────────────────────
class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.session_id"),
        nullable=False,
    )
    tx_id = Column(String(128), nullable=False)
    amount_usdc = Column(Numeric(18, 6), nullable=False)
    network = Column(String(64), nullable=False, default="algorand-testnet")
    simulation = Column(Boolean, nullable=False, default=True)
    delivered_at = Column(DateTime(timezone=True), default=_utcnow)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ─── capability_handshakes (Phase 2 — protocol compatibility record) ────────
class CapabilityHandshake(Base):
    __tablename__ = "capability_handshakes"

    handshake_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.session_id"), nullable=True,
    )
    buyer_enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    seller_enterprise_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("enterprises.enterprise_id"), nullable=False,
    )
    compatible = Column(Boolean, nullable=False)
    shared_protocols = Column(JSONB, default=list)
    shared_settlement_networks = Column(JSONB, default=list)
    shared_payment_methods = Column(JSONB, default=list)
    incompatibility_reasons = Column(JSONB, default=list)
    buyer_card_snapshot = Column(JSONB, nullable=True)
    seller_card_snapshot = Column(JSONB, nullable=True)
    selected_protocol = Column(String(100), nullable=True)
    selected_settlement = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
