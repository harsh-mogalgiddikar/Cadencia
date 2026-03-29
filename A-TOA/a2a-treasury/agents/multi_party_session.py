"""
agents/multi_party_session.py — Multi-party negotiation coordinator.

Allows ONE buyer to negotiate with MULTIPLE sellers simultaneously.
Each buyer-seller pair uses the existing DANP FSM.
The multi-party layer coordinates across them.

RULE 19: Escrow triggered for WINNING session ONLY.
         All other child sessions terminated as WALKAWAY.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Enterprise, MultiPartySession, Negotiation

logger = logging.getLogger("a2a_treasury.multi_party")


class MultiPartyCoordinator:
    """Coordinates multi-party negotiations."""

    async def create_multi_session(
        self,
        buyer_enterprise_id: str,
        seller_enterprise_ids: list[str],
        initial_offer_value: float,
        timeout_seconds: int,
        db_session: AsyncSession,
        redis_client,
    ) -> dict:
        """
        Create one child DANP session per seller via state_machine.create_session.
        Phase 4: Each child is a full BUYER_ANCHOR session so run_negotiation can proceed.
        """
        # Validate seller count
        if len(seller_enterprise_ids) < 2:
            raise ValueError("Multi-party session requires at least 2 sellers")
        if len(seller_enterprise_ids) > 5:
            raise ValueError("Multi-party session allows at most 5 sellers")

        from core.state_machine import DANPStateMachine
        from db.models import AgentConfig

        state_machine = DANPStateMachine()
        multi_id = uuid.uuid4()
        child_ids = []

        cfg_r = await db_session.execute(
            select(AgentConfig).where(
                AgentConfig.enterprise_id == uuid.UUID(buyer_enterprise_id)
            )
        )
        cfg = cfg_r.scalar_one_or_none()
        max_rounds = int(cfg.max_rounds) if cfg else 8

        for seller_id in seller_enterprise_ids:
            result = await state_machine.create_session(
                buyer_enterprise_id=buyer_enterprise_id,
                seller_enterprise_id=seller_id,
                initial_offer_value=initial_offer_value,
                milestone_template_id="tmpl-single-delivery",
                timeout_seconds=timeout_seconds,
                max_rounds=max_rounds,
                db_session=db_session,
                redis_client=redis_client,
            )
            session_id = result["session_id"]
            child_ids.append(session_id)
            await db_session.execute(
                update(Negotiation)
                .where(Negotiation.session_id == uuid.UUID(session_id))
                .values(multi_session_id=multi_id)
            )

        mps = MultiPartySession(
            id=multi_id,
            buyer_enterprise_id=uuid.UUID(buyer_enterprise_id),
            seller_ids=[str(s) for s in seller_enterprise_ids],
            child_session_ids=child_ids,
            status="ACTIVE",
            timeout_seconds=timeout_seconds,
        )
        db_session.add(mps)
        await db_session.flush()

        logger.info(
            "Multi-party session %s created: %d sellers, %d children",
            str(multi_id)[:8], len(seller_enterprise_ids), len(child_ids),
        )

        return {
            "multi_session_id": str(multi_id),
            "buyer_enterprise_id": buyer_enterprise_id,
            "seller_enterprise_ids": seller_enterprise_ids,
            "child_session_ids": child_ids,
            "status": "ACTIVE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "timeout_seconds": timeout_seconds,
        }

    async def run_multi_session(
        self,
        multi_session_id: str,
        db_session: AsyncSession,
        redis_client,
    ) -> dict:
        """
        Run all child sessions concurrently.
        When ALL are terminal, select winner (lowest AGREED value for buyer).
        """
        mid = uuid.UUID(multi_session_id)

        # Get multi-party record
        mps_r = await db_session.execute(
            select(MultiPartySession).where(MultiPartySession.id == mid)
        )
        mps = mps_r.scalar_one_or_none()
        if not mps:
            return {"error": "Multi-party session not found"}

        child_ids = mps.child_session_ids or []

        # Run each child session
        from agents.neutral_agent import NeutralProtocolEngine
        engine = NeutralProtocolEngine()

        async def _run_child(session_id_str: str) -> None:
            try:
                await engine.run_negotiation(session_id_str, db_session, redis_client)
            except Exception as e:
                logger.error("Child session %s failed: %s", session_id_str[:8], e)

        # Run concurrently
        await asyncio.gather(
            *[_run_child(sid) for sid in child_ids],
            return_exceptions=True,
        )

        # Evaluate results
        best_session_id = None
        best_value = float("inf")
        agreed_count = 0

        for sid in child_ids:
            neg_r = await db_session.execute(
                select(Negotiation).where(
                    Negotiation.session_id == uuid.UUID(sid)
                )
            )
            neg = neg_r.scalar_one_or_none()
            if neg and neg.status == "AGREED" and neg.final_agreed_value:
                agreed_count += 1
                val = float(neg.final_agreed_value)
                if val < best_value:
                    best_value = val
                    best_session_id = sid

        # Update multi-party record
        if best_session_id:
            mps.status = "CONCLUDED"
            mps.best_session_id = uuid.UUID(best_session_id)
            mps.best_offer_value = best_value
            mps.concluded_at = datetime.now(timezone.utc)

            # Terminate non-winning AGREED sessions as WALKAWAY (RULE 19)
            for sid in child_ids:
                if sid != best_session_id:
                    neg_r = await db_session.execute(
                        select(Negotiation).where(
                            Negotiation.session_id == uuid.UUID(sid)
                        )
                    )
                    neg = neg_r.scalar_one_or_none()
                    if neg and neg.status == "AGREED":
                        neg.status = "WALKAWAY"
                        neg.outcome = "MULTI_PARTY_LOSER"

            # Trigger escrow only for winner
            from blockchain.escrow_manager import escrow_manager
            try:
                await escrow_manager.trigger_escrow(best_session_id, db_session, redis_client)
            except Exception as e:
                logger.warning("Winner escrow trigger failed: %s", e)

            # Audit log
            from db.audit_logger import AuditLogger
            audit_logger = AuditLogger()
            await audit_logger.append(
                entity_type="multi_session",
                entity_id=str(mid),
                action="MULTI_SESSION_CONCLUDED",
                actor_id="system",
                payload={
                    "winner_session_id": best_session_id,
                    "best_offer": best_value,
                    "total_sessions": len(child_ids),
                    "agreed_count": agreed_count,
                },
                db_session=db_session,
            )
        else:
            mps.status = "EXPIRED"
            mps.concluded_at = datetime.now(timezone.utc)

            from db.audit_logger import AuditLogger
            audit_logger = AuditLogger()
            await audit_logger.append(
                entity_type="multi_session",
                entity_id=str(mid),
                action="MULTI_SESSION_NO_AGREEMENT",
                actor_id="system",
                payload={
                    "total_sessions": len(child_ids),
                    "agreed_count": 0,
                },
                db_session=db_session,
            )

        await db_session.flush()

        logger.info(
            "Multi-party %s concluded: status=%s winner=%s",
            str(mid)[:8], mps.status,
            best_session_id[:8] if best_session_id else "NONE",
        )

        return {
            "multi_session_id": multi_session_id,
            "status": mps.status,
            "best_session_id": best_session_id,
            "best_offer_value": best_value if best_session_id else None,
            "agreed_count": agreed_count,
            "total_sessions": len(child_ids),
        }

    async def get_multi_session_status(
        self, multi_session_id: str, db_session: AsyncSession
    ) -> dict:
        """Returns current multi-session state."""
        mid = uuid.UUID(multi_session_id)
        mps_r = await db_session.execute(
            select(MultiPartySession).where(MultiPartySession.id == mid)
        )
        mps = mps_r.scalar_one_or_none()
        if not mps:
            return {"error": "Not found"}

        # Get child session statuses
        children = []
        for sid in (mps.child_session_ids or []):
            neg_r = await db_session.execute(
                select(Negotiation).where(
                    Negotiation.session_id == uuid.UUID(sid)
                )
            )
            neg = neg_r.scalar_one_or_none()
            if neg:
                children.append({
                    "session_id": sid,
                    "status": neg.status,
                    "final_value": float(neg.final_agreed_value) if neg.final_agreed_value else None,
                    "rounds": neg.current_round,
                })

        return {
            "multi_session_id": multi_session_id,
            "status": mps.status,
            "buyer_enterprise_id": str(mps.buyer_enterprise_id),
            "seller_ids": mps.seller_ids,
            "child_sessions": children,
            "best_session_id": str(mps.best_session_id) if mps.best_session_id else None,
            "best_offer_value": float(mps.best_offer_value) if mps.best_offer_value else None,
            "created_at": mps.created_at.isoformat() if mps.created_at else None,
            "concluded_at": mps.concluded_at.isoformat() if mps.concluded_at else None,
        }

    async def get_leaderboard(
        self, multi_session_id: str, db_session: AsyncSession
    ) -> list[dict]:
        """Ranked list of offers across all child sessions."""
        mid = uuid.UUID(multi_session_id)
        mps_r = await db_session.execute(
            select(MultiPartySession).where(MultiPartySession.id == mid)
        )
        mps = mps_r.scalar_one_or_none()
        if not mps:
            return []

        entries = []
        for sid in (mps.child_session_ids or []):
            neg_r = await db_session.execute(
                select(Negotiation).where(
                    Negotiation.session_id == uuid.UUID(sid)
                )
            )
            neg = neg_r.scalar_one_or_none()
            if not neg:
                continue

            # Get seller name
            ent_r = await db_session.execute(
                select(Enterprise).where(
                    Enterprise.enterprise_id == neg.seller_enterprise_id
                )
            )
            ent = ent_r.scalar_one_or_none()

            entries.append({
                "session_id": sid,
                "seller_name": ent.legal_name if ent else "Unknown",
                "best_offer": float(neg.final_agreed_value) if neg.final_agreed_value else None,
                "status": neg.status,
                "rounds_taken": neg.current_round or 0,
            })

        # Sort: AGREED first by price ascending, then non-AGREED
        agreed = sorted(
            [e for e in entries if e["status"] == "AGREED" and e["best_offer"]],
            key=lambda x: x["best_offer"],
        )
        others = [e for e in entries if e["status"] != "AGREED" or not e["best_offer"]]

        ranked = agreed + others
        for i, entry in enumerate(ranked):
            entry["rank"] = i + 1

        return ranked


# Module-level singleton
multi_party_coordinator = MultiPartyCoordinator()
