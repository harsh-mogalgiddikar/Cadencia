"""
treasury/analytics.py — Treasury analytics for negotiation insights.

Provides time-series, strategy performance, counterparty analysis,
and LLM advisory performance metrics.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog, Enterprise, Negotiation, Offer

logger = logging.getLogger("a2a_treasury.analytics")


class TreasuryAnalytics:
    """Analytics engine for treasury intelligence."""

    async def get_negotiation_timeline(
        self,
        enterprise_id: str,
        days: int = 30,
        db_session: AsyncSession | None = None,
    ) -> list[dict]:
        """Daily negotiation activity for last N days."""
        if not db_session:
            return []

        eid = uuid.UUID(enterprise_id)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all sessions for enterprise since cutoff
        buyer_r = await db_session.execute(
            select(Negotiation).where(
                Negotiation.buyer_enterprise_id == eid,
                Negotiation.initiated_at >= cutoff,
            )
        )
        seller_r = await db_session.execute(
            select(Negotiation).where(
                Negotiation.seller_enterprise_id == eid,
                Negotiation.initiated_at >= cutoff,
            )
        )
        sessions = list(buyer_r.scalars().all()) + list(seller_r.scalars().all())

        # Group by date
        by_date: dict[str, dict] = {}
        for s in sessions:
            day = s.initiated_at.strftime("%Y-%m-%d") if s.initiated_at else "unknown"
            if day not in by_date:
                by_date[day] = {
                    "date": day,
                    "sessions_started": 0,
                    "sessions_agreed": 0,
                    "total_inr_value": 0.0,
                    "rounds_sum": 0,
                    "rounds_count": 0,
                }
            by_date[day]["sessions_started"] += 1
            if s.status == "AGREED":
                by_date[day]["sessions_agreed"] += 1
                by_date[day]["total_inr_value"] += float(s.final_agreed_value or 0)
            if s.current_round:
                by_date[day]["rounds_sum"] += s.current_round
                by_date[day]["rounds_count"] += 1

        result = []
        for d in sorted(by_date.keys()):
            entry = by_date[d]
            entry["avg_rounds"] = round(
                entry["rounds_sum"] / entry["rounds_count"], 1
            ) if entry["rounds_count"] else 0.0
            del entry["rounds_sum"]
            del entry["rounds_count"]
            result.append(entry)

        return result

    async def get_strategy_performance(
        self,
        enterprise_id: str,
        db_session: AsyncSession | None = None,
    ) -> dict:
        """Breakdown of outcomes by strategy_tag."""
        if not db_session:
            return {}

        eid = uuid.UUID(enterprise_id)

        # Get all offers for this enterprise's sessions
        buyer_sids = await db_session.execute(
            select(Negotiation.session_id).where(
                Negotiation.buyer_enterprise_id == eid
            )
        )
        seller_sids = await db_session.execute(
            select(Negotiation.session_id).where(
                Negotiation.seller_enterprise_id == eid
            )
        )
        session_ids = [r[0] for r in buyer_sids.all()] + [
            r[0] for r in seller_sids.all()
        ]

        if not session_ids:
            return {}

        offers_r = await db_session.execute(
            select(Offer).where(Offer.session_id.in_(session_ids))
        )
        offers = offers_r.scalars().all()

        # Group by strategy_tag
        by_tag: dict[str, dict] = {}
        for o in offers:
            tag = o.strategy_tag or "unknown"
            if tag not in by_tag:
                by_tag[tag] = {"count": 0, "confidence_sum": 0.0}
            by_tag[tag]["count"] += 1
            by_tag[tag]["confidence_sum"] += float(o.confidence or 0)

        return {
            tag: {
                "count": data["count"],
                "avg_utility": round(data["confidence_sum"] / data["count"], 4)
                if data["count"] else 0.0,
            }
            for tag, data in by_tag.items()
        }

    async def get_counterparty_analysis(
        self,
        enterprise_id: str,
        db_session: AsyncSession | None = None,
    ) -> list[dict]:
        """Per-counterparty negotiation history."""
        if not db_session:
            return []

        eid = uuid.UUID(enterprise_id)

        # Sessions as buyer (counterparty = seller)
        buyer_r = await db_session.execute(
            select(Negotiation).where(Negotiation.buyer_enterprise_id == eid)
        )
        # Sessions as seller (counterparty = buyer)
        seller_r = await db_session.execute(
            select(Negotiation).where(Negotiation.seller_enterprise_id == eid)
        )

        counterparties: dict[str, dict] = {}
        for s in buyer_r.scalars().all():
            cp_id = str(s.seller_enterprise_id)
            if cp_id not in counterparties:
                counterparties[cp_id] = {
                    "sessions": [], "counterparty_id": cp_id,
                }
            counterparties[cp_id]["sessions"].append(s)

        for s in seller_r.scalars().all():
            cp_id = str(s.buyer_enterprise_id)
            if cp_id not in counterparties:
                counterparties[cp_id] = {
                    "sessions": [], "counterparty_id": cp_id,
                }
            counterparties[cp_id]["sessions"].append(s)

        result = []
        for cp_id, data in counterparties.items():
            sessions = data["sessions"]
            agreed = [s for s in sessions if s.status == "AGREED"]
            avg_value = (
                sum(float(s.final_agreed_value or 0) for s in agreed) / len(agreed)
                if agreed else 0.0
            )
            rounds = [s.current_round for s in sessions if s.current_round]
            avg_rounds = sum(rounds) / len(rounds) if rounds else 0.0
            last = max(
                (s.initiated_at for s in sessions if s.initiated_at), default=None
            )

            # Get enterprise name
            ent_r = await db_session.execute(
                select(Enterprise).where(
                    Enterprise.enterprise_id == uuid.UUID(cp_id)
                )
            )
            ent = ent_r.scalar_one_or_none()

            result.append({
                "counterparty_id": cp_id,
                "counterparty_name": ent.legal_name if ent else "Unknown",
                "sessions_count": len(sessions),
                "agreed_count": len(agreed),
                "avg_agreed_value": round(avg_value, 2),
                "avg_rounds": round(avg_rounds, 1),
                "last_session_at": last.isoformat() if last else None,
            })

        return sorted(result, key=lambda x: x["sessions_count"], reverse=True)

    async def get_llm_performance(
        self,
        session_id: str,
        db_session: AsyncSession | None = None,
    ) -> dict:
        """LLM advisory performance for a session."""
        if not db_session:
            return {}

        sid = uuid.UUID(session_id)

        # Get LLM_ADVISORY_USED entries from audit logs
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_id == sid,
                AuditLog.action == "LLM_ADVISORY_USED",
            )
        )
        entries = result.scalars().all()

        total_calls = len(entries)
        fallback_count = 0
        modifiers = []
        opponent_types = set()

        for e in entries:
            payload = e.payload or {}
            if payload.get("fallback_used"):
                fallback_count += 1
            mod = payload.get("recommended_modifier")
            if mod is not None:
                modifiers.append(float(mod))
            opp = payload.get("opponent_type")
            if opp:
                opponent_types.add(opp)

        return {
            "total_calls": total_calls,
            "fallback_count": fallback_count,
            "avg_modifier": round(sum(modifiers) / len(modifiers), 4) if modifiers else 0.0,
            "opponent_types_seen": list(opponent_types),
            "circuit_breaker_triggered": fallback_count > 2,
        }


# Module-level singleton
treasury_analytics = TreasuryAnalytics()
