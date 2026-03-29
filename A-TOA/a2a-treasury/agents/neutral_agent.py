"""
agents/neutral_agent.py — Neutral Protocol Engine.

Orchestrates autonomous negotiation: runs BuyerAgent and SellerAgent concurrently,
monitors for terminal state, triggers escrow on AGREED.
ZERO financial position. Pure routing.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.buyer_agent import BuyerAgent
from agents.seller_agent import SellerAgent
from a2a_protocol.task_manager import A2ATaskManager
from core.state_machine import TERMINAL_STATES
from db.audit_logger import AuditLogger
from db.models import Negotiation
from sqlalchemy import select

logger = logging.getLogger("a2a_treasury")
audit_logger = AuditLogger()


class NeutralProtocolEngine:
    """
    Orchestrates a complete autonomous negotiation.
    Runs buyer/seller turns sequentially in a loop.
    Monitors session for terminal state. Triggers escrow on AGREED.
    """

    async def run_negotiation(
        self,
        session_id: str,
        db_session: Any,
        redis_client: Any,
    ) -> dict:
        """
        Sequential turn-based autonomous negotiation:
        1. Check whose turn it is via expected_turn
        2. Run that agent's turn through the 4-layer pipeline
        3. Commit, sleep for rate limit, repeat
        4. On terminal: trigger escrow if AGREED, log completion
        """
        from agents.pipeline import run_agent_turn, _load_agent_config_dict
        from a2a_protocol.task_manager import A2ATaskManager

        result = await db_session.execute(
            select(Negotiation).where(
                Negotiation.session_id == uuid.UUID(session_id),
            ),
        )
        neg = result.scalar_one_or_none()
        if neg is None:
            raise ValueError(f"Session not found: {session_id}")
        if neg.status != "BUYER_ANCHOR":
            return {
                "session_id": session_id,
                "status": neg.status,
                "message": "Session not in BUYER_ANCHOR; cannot start autonomous run",
            }

        task_manager = A2ATaskManager()
        timeout_at = neg.timeout_at
        max_iterations = 50  # Safety limit

        for iteration in range(max_iterations):
            # Check timeout
            if timeout_at and datetime.now(timezone.utc) >= timeout_at:
                logger.warning("Session %s timed out", session_id)
                break

            # Read current state
            state = await redis_client.get_session_state(session_id)
            if state is None:
                state = await redis_client.rebuild_from_postgres(
                    session_id, db_session
                )
            if state is None:
                logger.error("Session %s state not found", session_id)
                break

            status = state.get("status", "")
            if status in TERMINAL_STATES:
                logger.info("Session %s reached terminal: %s", session_id, status)
                break

            expected = state.get("expected_turn", "seller")
            current_round = state.get("current_round", 1)

            # Load agent config
            if expected == "buyer":
                enterprise_id = state["buyer_enterprise_id"]
            else:
                enterprise_id = state["seller_enterprise_id"]

            # Retry agent config lookup (handles timing race in multi-party)
            agent_config = None
            for attempt in range(3):
                try:
                    agent_config = await _load_agent_config_dict(
                        enterprise_id, expected, db_session
                    )
                    break
                except (RuntimeError, Exception) as cfg_err:
                    if attempt < 2:
                        logger.debug(
                            "Session %s: agent config for %s not found (attempt %d/3), retrying...",
                            session_id, expected, attempt + 1,
                        )
                        await asyncio.sleep(1.0)
                    else:
                        logger.warning(
                            "Session %s: No agent config for %s enterprise %s after 3 attempts — transitioning to WALKAWAY",
                            session_id, expected, enterprise_id,
                        )

            if agent_config is None:
                # Transition to WALKAWAY so session doesn't hang forever
                neg_result = await db_session.execute(
                    select(Negotiation).where(
                        Negotiation.session_id == uuid.UUID(session_id),
                    ),
                )
                neg_row = neg_result.scalar_one_or_none()
                if neg_row and neg_row.status not in TERMINAL_STATES:
                    neg_row.status = "WALKAWAY"
                    neg_row.outcome = f"NO_AGENT_CONFIG_{expected.upper()}"
                    await db_session.commit()
                    await redis_client.set_session_state(session_id, {
                        **state,
                        "status": "WALKAWAY",
                        "outcome": neg_row.outcome,
                    })
                break

            try:
                await run_agent_turn(
                    session_id=session_id,
                    agent_role=expected,
                    current_round=current_round,
                    session_state=state,
                    agent_config=agent_config,
                    db_session=db_session,
                    redis_client=redis_client,
                    task_manager=task_manager,
                )
                await db_session.commit()
                logger.info(
                    "Session %s: %s completed turn (round %d)",
                    session_id, expected, current_round,
                )
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Rate limit" in err_str:
                    logger.debug("Rate-limited, backing off")
                    await asyncio.sleep(3.0)
                    continue
                # Detect POLICY_BREACH from guardrail engine — transition to terminal
                if "POLICY_BREACH" in err_str:
                    logger.warning(
                        "Session %s: POLICY_BREACH detected — transitioning to terminal",
                        session_id,
                    )
                    try:
                        await db_session.rollback()
                        neg_pb = await db_session.execute(
                            select(Negotiation).where(
                                Negotiation.session_id == uuid.UUID(session_id),
                            ),
                        )
                        neg_row_pb = neg_pb.scalar_one_or_none()
                        if neg_row_pb and neg_row_pb.status not in TERMINAL_STATES:
                            neg_row_pb.status = "POLICY_BREACH"
                            neg_row_pb.outcome = f"GUARDRAIL_{expected.upper()}"
                            await db_session.commit()
                            await redis_client.set_session_state(session_id, {
                                **state,
                                "status": "POLICY_BREACH",
                                "outcome": neg_row_pb.outcome,
                            })
                    except Exception as pb_err:
                        logger.exception("Failed to set POLICY_BREACH: %s", pb_err)
                    break
                logger.exception(
                    "Session %s: %s turn failed: %s",
                    session_id, expected, e,
                )
                await db_session.rollback()

            # Sleep to respect rate limit
            await asyncio.sleep(2.5)

        # Read final state
        final_state = await redis_client.get_session_state(session_id)
        if final_state is None:
            final_state = await redis_client.rebuild_from_postgres(
                session_id, db_session
            ) or {}

        status = final_state.get("status", "UNKNOWN")
        if status == "AGREED":
            try:
                from blockchain.escrow_manager import EscrowManager

                escrow_manager = EscrowManager()
                escrow_result = await escrow_manager.trigger_escrow(
                    session_id, db_session, redis_client
                )
                await db_session.commit()
                logger.info(
                    "Escrow triggered for session %s: %s",
                    session_id,
                    escrow_result.get("status"),
                )
            except Exception as e:
                logger.exception("Escrow trigger failed: %s", e)

        await audit_logger.append(
            entity_type="negotiation",
            entity_id=session_id,
            action="A2A_NEGOTIATION_COMPLETE",
            actor_id="neutral",
            payload={"status": status, "session_id": session_id},
            db_session=db_session,
        )
        await db_session.commit()

        # ── Phase 3 ACF: Merkle root + on-chain anchor ──────────────────
        if status in TERMINAL_STATES:
            try:
                from core.merkle_service import MerkleService
                merkle_root = await MerkleService.compute_and_store(
                    str(session_id), db_session,
                )
                if merkle_root:
                    # Count leaves for audit log
                    from db.models import AuditLog as _AL
                    _cnt_result = await db_session.execute(
                        select(_AL).where(
                            _AL.entity_id == uuid.UUID(session_id),
                        ),
                    )
                    _leaf_count = len(_cnt_result.scalars().all())
                    await audit_logger.append(
                        entity_type="negotiation",
                        entity_id=session_id,
                        action="MERKLE_ROOT_COMPUTED",
                        actor_id="system",
                        payload={
                            "merkle_root": merkle_root,
                            "leaf_count": _leaf_count,
                        },
                        db_session=db_session,
                    )
                    await db_session.commit()

                    # Anchor on-chain
                    try:
                        from core.anchor_service import AnchorService
                        anchor_result = await AnchorService.anchor_session(
                            str(session_id), merkle_root, db_session,
                        )
                        if anchor_result.get("anchored"):
                            await audit_logger.append(
                                entity_type="negotiation",
                                entity_id=session_id,
                                action="AUDIT_ANCHORED_ON_CHAIN",
                                actor_id="system",
                                payload=anchor_result,
                                db_session=db_session,
                            )
                            await db_session.commit()
                    except Exception as anchor_err:
                        logger.warning(
                            "Anchor failed for session %s: %s (non-blocking)",
                            session_id, anchor_err,
                        )
            except Exception as merkle_err:
                logger.warning(
                    "Merkle computation failed for session %s: %s (non-blocking)",
                    session_id, merkle_err,
                )

        return {
            "session_id": session_id,
            "status": status,
            "current_round": final_state.get("current_round"),
            "outcome": final_state.get("outcome"),
            "final_agreed_value": final_state.get("last_buyer_offer") or final_state.get("last_seller_offer"),
        }
