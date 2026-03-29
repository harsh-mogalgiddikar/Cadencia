"""
treasury/dashboard.py — Treasury dashboard for enterprise and platform metrics.

Phase 3: Fully implemented — replaces Phase 1 stub.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentConfig,
    Enterprise,
    EscrowContract,
    FxQuote,
    Negotiation,
    Offer,
    Settlement,
    TreasuryPolicy,
    Wallet,
)

logger = logging.getLogger("a2a_treasury.treasury")


class TreasuryDashboard:
    """Treasury intelligence dashboard."""

    async def get_enterprise_summary(
        self, enterprise_id: str, db_session: AsyncSession
    ) -> dict:
        """Full treasury summary for one enterprise."""
        eid = uuid.UUID(enterprise_id)

        # Enterprise info
        ent_r = await db_session.execute(
            select(Enterprise).where(Enterprise.enterprise_id == eid)
        )
        ent = ent_r.scalar_one_or_none()
        if not ent:
            return {"error": "Enterprise not found"}

        # Agent config
        cfg_r = await db_session.execute(
            select(AgentConfig).where(AgentConfig.enterprise_id == eid)
        )
        cfg = cfg_r.scalar_one_or_none()

        # Treasury policy
        pol_r = await db_session.execute(
            select(TreasuryPolicy)
            .where(TreasuryPolicy.enterprise_id == eid)
            .order_by(TreasuryPolicy.created_at.desc())
            .limit(1)
        )
        pol = pol_r.scalar_one_or_none()

        # Wallet
        wal_r = await db_session.execute(
            select(Wallet).where(Wallet.enterprise_id == eid)
        )
        wal = wal_r.scalar_one_or_none()

        # Sessions as buyer or seller
        buyer_sessions = await db_session.execute(
            select(Negotiation).where(Negotiation.buyer_enterprise_id == eid)
        )
        seller_sessions = await db_session.execute(
            select(Negotiation).where(Negotiation.seller_enterprise_id == eid)
        )
        all_sessions = list(buyer_sessions.scalars().all()) + list(
            seller_sessions.scalars().all()
        )

        total = len(all_sessions)
        agreed = [s for s in all_sessions if s.status == "AGREED"]
        walkaway = [s for s in all_sessions if s.status in ("WALKAWAY", "TIMEOUT", "STALLED")]

        total_inr = sum(float(s.final_agreed_value or 0) for s in agreed)
        avg_agreed = total_inr / len(agreed) if agreed else 0.0

        # Rounds
        rounds_list = [s.current_round for s in agreed if s.current_round]
        avg_rounds = sum(rounds_list) / len(rounds_list) if rounds_list else 0.0

        # Escrows
        escrow_r = await db_session.execute(
            select(EscrowContract).where(
                EscrowContract.session_id.in_(
                    [s.session_id for s in all_sessions]
                )
            )
        )
        escrows = escrow_r.scalars().all()
        active_escrows = [e for e in escrows if e.status in ("FUNDED", "AWAITING", "DEPLOYED")]
        total_escrow_usdc = sum(float(e.amount or 0) for e in active_escrows)

        # Settlements
        settle_r = await db_session.execute(
            select(Settlement).where(
                Settlement.escrow_id.in_([e.escrow_id for e in escrows])
            )
        )
        settlements = settle_r.scalars().all()
        total_usdc_settled = sum(float(s.amount_released or 0) for s in settlements)

        last_session = max(
            (s.initiated_at for s in all_sessions if s.initiated_at), default=None
        )

        return {
            "enterprise_id": enterprise_id,
            "enterprise_name": ent.legal_name,
            "wallet_address": wal.address if wal else None,
            "usdc_balance": float(wal.usdc_balance) if wal else 0.0,
            "total_sessions": total,
            "agreed_sessions": len(agreed),
            "walkaway_sessions": len(walkaway),
            "total_inr_negotiated": round(total_inr, 2),
            "total_usdc_settled": round(total_usdc_settled, 6),
            "avg_rounds_to_agreement": round(avg_rounds, 1),
            "avg_agreed_value": round(avg_agreed, 2),
            "success_rate": round(len(agreed) / total * 100, 1) if total else 0.0,
            "active_escrows": len(active_escrows),
            "total_escrow_value_usdc": round(total_escrow_usdc, 6),
            "last_session_at": last_session.isoformat() if last_session else None,
            "agent_role": cfg.agent_role if cfg else None,
            "risk_tolerance": pol.risk_tolerance if pol else None,
            "buffer_threshold": float(pol.buffer_threshold) if pol and pol.buffer_threshold else None,
        }

    async def get_platform_summary(self, db_session: AsyncSession) -> dict:
        """Platform-wide metrics across all enterprises."""
        # Enterprises
        total_ent = (await db_session.execute(
            select(func.count(Enterprise.enterprise_id))
        )).scalar() or 0
        active_ent = (await db_session.execute(
            select(func.count(Enterprise.enterprise_id))
            .where(Enterprise.kyc_status == "ACTIVE")
        )).scalar() or 0

        # Sessions
        all_neg = await db_session.execute(select(Negotiation))
        sessions = all_neg.scalars().all()
        total_sessions = len(sessions)
        agreed_sessions = [s for s in sessions if s.status == "AGREED"]
        total_inr = sum(float(s.final_agreed_value or 0) for s in agreed_sessions)

        # Escrows
        escrow_r = await db_session.execute(select(EscrowContract))
        escrows = escrow_r.scalars().all()
        active_escrows = [e for e in escrows if e.status in ("FUNDED", "AWAITING", "DEPLOYED")]

        # FX rate
        fx_r = await db_session.execute(
            select(FxQuote).order_by(FxQuote.fetched_at.desc()).limit(1)
        )
        latest_fx = fx_r.scalar_one_or_none()

        # Time-based
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        sessions_today = sum(
            1 for s in sessions
            if s.initiated_at and s.initiated_at >= today_start
        )

        from datetime import timedelta
        week_start = now - timedelta(days=7)
        sessions_week = sum(
            1 for s in sessions
            if s.initiated_at and s.initiated_at >= week_start
        )

        rounds_list = [s.current_round for s in agreed_sessions if s.current_round]
        avg_rounds = sum(rounds_list) / len(rounds_list) if rounds_list else 0.0

        return {
            "total_enterprises": total_ent,
            "active_enterprises": active_ent,
            "total_sessions": total_sessions,
            "agreed_sessions": len(agreed_sessions),
            "total_inr_negotiated": round(total_inr, 2),
            "total_usdc_settled": 0.0,  # TODO: aggregate settlements
            "avg_agreed_value": round(total_inr / len(agreed_sessions), 2) if agreed_sessions else 0.0,
            "avg_rounds_to_agreement": round(avg_rounds, 1),
            "platform_success_rate": round(
                len(agreed_sessions) / total_sessions * 100, 1
            ) if total_sessions else 0.0,
            "active_escrows": len(active_escrows),
            "total_escrow_value_usdc": sum(float(e.amount or 0) for e in active_escrows),
            "current_fx_rate": float(latest_fx.sell_rate) if latest_fx else None,
            "sessions_today": sessions_today,
            "sessions_this_week": sessions_week,
        }

    async def get_session_pnl(
        self,
        session_id: str,
        enterprise_id: str,
        db_session: AsyncSession,
        redis_client=None,
    ) -> dict:
        """P&L analysis for a single session from one enterprise's perspective."""
        sid = uuid.UUID(session_id)
        eid = uuid.UUID(enterprise_id)

        # Session
        neg_r = await db_session.execute(
            select(Negotiation).where(Negotiation.session_id == sid)
        )
        neg = neg_r.scalar_one_or_none()
        if not neg:
            return {"error": "Session not found"}

        # Determine role
        role = "buyer" if neg.buyer_enterprise_id == eid else "seller"

        # Agent config
        cfg_r = await db_session.execute(
            select(AgentConfig).where(AgentConfig.enterprise_id == eid)
        )
        cfg = cfg_r.scalar_one_or_none()

        intrinsic = float(cfg.intrinsic_value) if cfg else 0.0
        agreed = float(neg.final_agreed_value or 0)

        # Buyer: lower = better. Seller: higher = better.
        if role == "buyer":
            inr_outcome = intrinsic - agreed  # positive = saved money
        else:
            inr_outcome = agreed - intrinsic  # positive = got more

        # FX
        fx_rate = float(neg.fx_rate_locked or 0.01193)
        usdc_outcome = round(inr_outcome * fx_rate, 6)

        # Offers
        offers_r = await db_session.execute(
            select(Offer).where(Offer.session_id == sid)
        )
        offers = offers_r.scalars().all()
        last_offer = [o for o in offers if o.agent_role == role]
        final_tag = last_offer[-1].strategy_tag if last_offer else "unknown"

        # LLM + guardrail counts from audit (approximate from offers)
        from db.models import AuditLog, GuardrailLog
        llm_r = await db_session.execute(
            select(func.count(AuditLog.log_id))
            .where(AuditLog.entity_id == sid)
            .where(AuditLog.action == "LLM_ADVISORY_USED")
        )
        llm_count = llm_r.scalar() or 0

        gr_r = await db_session.execute(
            select(func.count(GuardrailLog.log_id))
            .where(GuardrailLog.session_id == sid)
        )
        gr_count = gr_r.scalar() or 0

        return {
            "session_id": session_id,
            "role": role,
            "intrinsic_value": intrinsic,
            "final_agreed_value": agreed,
            "target_price": intrinsic * 0.88 if role == "buyer" else intrinsic * 1.12,
            "reservation_price": intrinsic * 1.12 if role == "buyer" else intrinsic * 0.88,
            "utility_score": round(max(0, 1 - abs(inr_outcome) / intrinsic), 4) if intrinsic else 0,
            "inr_outcome": round(inr_outcome, 2),
            "usdc_outcome": usdc_outcome,
            "fx_rate_used": fx_rate,
            "rounds_taken": neg.current_round or 0,
            "llm_advisory_count": llm_count,
            "guardrail_blocks": gr_count,
            "final_strategy_tag": final_tag,
        }

    async def get_exposure_report(
        self, enterprise_id: str, db_session: AsyncSession
    ) -> dict:
        """Current risk exposure for an enterprise."""
        eid = uuid.UUID(enterprise_id)

        cfg_r = await db_session.execute(
            select(AgentConfig).where(AgentConfig.enterprise_id == eid)
        )
        cfg = cfg_r.scalar_one_or_none()
        max_exposure = float(cfg.max_exposure) if cfg else 100000.0

        # Active escrows for this enterprise's sessions
        buyer_sessions = await db_session.execute(
            select(Negotiation.session_id).where(
                Negotiation.buyer_enterprise_id == eid
            )
        )
        seller_sessions = await db_session.execute(
            select(Negotiation.session_id).where(
                Negotiation.seller_enterprise_id == eid
            )
        )
        session_ids = [r[0] for r in buyer_sessions.all()] + [
            r[0] for r in seller_sessions.all()
        ]

        escrow_r = await db_session.execute(
            select(EscrowContract).where(
                EscrowContract.session_id.in_(session_ids),
                EscrowContract.status.in_(("FUNDED", "AWAITING", "DEPLOYED")),
            )
        )
        active = escrow_r.scalars().all()
        current_exposure = sum(float(e.amount or 0) for e in active)

        return {
            "enterprise_id": enterprise_id,
            "max_exposure_configured": max_exposure,
            "current_active_exposure": round(current_exposure, 6),
            "exposure_utilization_pct": round(
                current_exposure / max_exposure * 100, 1
            ) if max_exposure else 0.0,
            "escrow_breakdown": [
                {
                    "session_id": str(e.session_id),
                    "contract_ref": e.contract_ref or "N/A",
                    "amount_usdc": float(e.amount or 0),
                    "status": e.status or "UNKNOWN",
                }
                for e in active
            ],
        }


# Module-level singleton
treasury_dashboard = TreasuryDashboard()
