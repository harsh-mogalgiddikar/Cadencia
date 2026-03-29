"""
core/state_machine.py — DANP Finite State Machine.

This is the CORE of Phase 1. Implements the full Decentralized Autonomous
Negotiation Protocol state machine with all transitions.

Active states:  INIT, BUYER_ANCHOR, SELLER_RESPONSE, ROUND_LOOP
Terminal states: AGREED, WALKAWAY, TIMEOUT, ROUND_LIMIT, STALLED, POLICY_BREACH
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.guardrails import GuardrailEngine
from core.valuation import build_valuation_snapshot
from db.audit_logger import AuditLogger
from db.models import AgentConfig, Enterprise, Negotiation, Offer, TreasuryPolicy, Wallet

TERMINAL_STATES = frozenset({
    "AGREED", "WALKAWAY", "TIMEOUT", "ROUND_LIMIT", "STALLED", "POLICY_BREACH",
})

guardrail_engine = GuardrailEngine()
audit_logger = AuditLogger()


class DANPStateMachine:
    """DANP FSM — single entry-point for all negotiation transitions."""

    # ─── session creation ───────────────────────────────────────────────
    async def create_session(
        self,
        buyer_enterprise_id: str,
        seller_enterprise_id: str,
        initial_offer_value: float,
        milestone_template_id: str,
        timeout_seconds: int,
        max_rounds: int,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> dict:
        """Create a new negotiation session after full validation."""

        # ── Pre-creation validation ──────────────────────────────────────
        # 1. Buyer exists and is ACTIVE
        buyer = await self._get_active_enterprise(
            buyer_enterprise_id, "Buyer", db_session,
        )

        # 2. Seller exists and is ACTIVE
        seller = await self._get_active_enterprise(
            seller_enterprise_id, "Seller", db_session,
        )

        # 3. Different parties
        if str(buyer_enterprise_id) == str(seller_enterprise_id):
            raise HTTPException(
                status_code=422,
                detail="buyer_enterprise_id and seller_enterprise_id must differ",
            )

        # 4. Buyer has agent_config
        buyer_config = await self._get_agent_config(
            buyer_enterprise_id, "Buyer", db_session,
        )

        # 5. Buyer has treasury_policy
        await self._get_treasury_policy(
            buyer_enterprise_id, "Buyer", db_session,
        )

        # 6. initial_offer_value <= budget_ceiling
        if buyer_config.budget_ceiling is not None:
            if initial_offer_value > float(buyer_config.budget_ceiling):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"initial_offer_value {initial_offer_value} exceeds "
                        f"buyer budget_ceiling {buyer_config.budget_ceiling}"
                    ),
                )

        # 7. initial_offer_value <= max_exposure
        if initial_offer_value > float(buyer_config.max_exposure):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"initial_offer_value {initial_offer_value} exceeds "
                    f"buyer max_exposure {buyer_config.max_exposure}"
                ),
            )

        # Get seller config (needed for valuation)
        seller_config = await self._get_agent_config(
            seller_enterprise_id, "Seller", db_session,
        )

        # ── Compute valuations ───────────────────────────────────────────
        buyer_config_dict = self._config_to_dict(buyer_config, "buyer")
        seller_config_dict = self._config_to_dict(seller_config, "seller")

        buyer_snapshot = build_valuation_snapshot(buyer_config_dict)
        seller_snapshot = build_valuation_snapshot(seller_config_dict)

        # ── Create session ───────────────────────────────────────────────
        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        timeout_at = now + timedelta(seconds=timeout_seconds)

        negotiation = Negotiation(
            session_id=session_id,
            buyer_enterprise_id=uuid.UUID(str(buyer_enterprise_id)),
            seller_enterprise_id=uuid.UUID(str(seller_enterprise_id)),
            status="BUYER_ANCHOR",
            max_rounds=max_rounds,
            current_round=1,
            timeout_at=timeout_at,
            milestone_template_id=milestone_template_id,
            last_buyer_offer=Decimal(str(initial_offer_value)),
        )
        db_session.add(negotiation)

        # Insert the buyer's opening offer
        opening_offer = Offer(
            offer_id=uuid.uuid4(),
            session_id=session_id,
            agent_role="buyer",
            value=Decimal(str(initial_offer_value)),
            action="counter",
            round=1,
            confidence=Decimal("1.000"),
            strategy_tag="anchor",
            rationale="Opening anchor offer",
        )
        db_session.add(opening_offer)

        await db_session.flush()

        # ── Redis writes ─────────────────────────────────────────────────
        state = {
            "session_id": str(session_id),
            "buyer_enterprise_id": str(buyer_enterprise_id),
            "seller_enterprise_id": str(seller_enterprise_id),
            "status": "BUYER_ANCHOR",
            "max_rounds": max_rounds,
            "current_round": 1,
            "timeout_at": timeout_at.isoformat(),
            "outcome": None,
            "last_buyer_offer": initial_offer_value,
            "last_seller_offer": None,
            "stall_counter": 0,
            "buyer_consecutive_failures": 0,
            "seller_consecutive_failures": 0,
            "expected_turn": "seller",
        }
        await redis_client.set_session_state(
            str(session_id), state, timeout_seconds,
        )

        # Store valuation snapshots (keyed by role for retrieval)
        await redis_client.set_valuation_snapshot(
            f"{session_id}:buyer", buyer_snapshot,
        )
        await redis_client.set_valuation_snapshot(
            f"{session_id}:seller", seller_snapshot,
        )

        # ── Audit log ────────────────────────────────────────────────────
        await audit_logger.append(
            entity_type="negotiation",
            entity_id=str(session_id),
            action="SESSION_CREATED",
            actor_id=str(buyer_enterprise_id),
            payload={
                "buyer_enterprise_id": str(buyer_enterprise_id),
                "seller_enterprise_id": str(seller_enterprise_id),
                "initial_offer_value": initial_offer_value,
                "max_rounds": max_rounds,
                "timeout_seconds": timeout_seconds,
            },
            db_session=db_session,
        )

        return {
            "session_id": str(session_id),
            "status": "BUYER_ANCHOR",
            "buyer_enterprise_id": str(buyer_enterprise_id),
            "seller_enterprise_id": str(seller_enterprise_id),
            "max_rounds": max_rounds,
            "timeout_at": timeout_at.isoformat(),
            "created_at": now.isoformat(),
        }

    # ─── process action ─────────────────────────────────────────────────
    async def process_action(
        self,
        action: dict,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> dict:
        """
        SINGLE entry point for all agent actions.
        Executes validation pipeline in strict order.
        """
        session_id = action["session_id"]
        agent_role = action["agent_role"]
        action_type = action["action"]
        offer_value = action.get("offer_value")
        round_num = action["round"]

        # STEP 1: RATE LIMIT
        allowed = await redis_client.check_rate_limit(session_id, agent_role)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit: 1 action per 2 seconds",
            )

        # STEP 2: LOAD SESSION STATE
        state = await redis_client.get_session_state(session_id)
        if state is None:
            state = await redis_client.rebuild_from_postgres(
                session_id, db_session,
            )
        if state is None:
            raise HTTPException(
                status_code=404, detail="Session not found or expired",
            )

        # STEP 3: TERMINAL STATE CHECK
        if state["status"] in TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"Session is in terminal state: {state['status']}",
            )

        # STEP 4: TIMEOUT CHECK
        timeout_at = datetime.fromisoformat(state["timeout_at"])
        if datetime.now(timezone.utc) >= timeout_at:
            await self._transition_to_terminal(
                session_id, "TIMEOUT", db_session, redis_client,
            )
            raise HTTPException(status_code=409, detail="Session timed out")

        # STEP 5: TURN ORDER CHECK
        expected_turn = self._get_expected_turn(state)
        if agent_role != expected_turn:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "TURN_VIOLATION",
                    "expected": expected_turn,
                    "received": agent_role,
                },
            )

        # STEP 6: ROUND NUMBER VALIDATION
        current_round = state["current_round"]
        valid_round = False
        if action_type == "counter":
            # New counter offer: round should be current_round + 1
            # (except for first seller response in BUYER_ANCHOR where round can be 1)
            if state["status"] == "BUYER_ANCHOR" and round_num == 1:
                valid_round = True
            elif round_num == current_round + 1:
                valid_round = True
            elif round_num == current_round:
                valid_round = True
        else:
            # accept/reject: round can be current_round
            if round_num == current_round:
                valid_round = True
            elif round_num == current_round + 1:
                valid_round = True

        if not valid_round:
            await redis_client.increment_failure_count(session_id, agent_role)
            raise HTTPException(
                status_code=422, detail="Invalid round number",
            )

        # STEP 7: GUARDRAIL ENFORCEMENT
        snapshot_key = f"{session_id}:{agent_role}"
        snapshot = await redis_client.get_valuation_snapshot(snapshot_key)

        # Load agent_config from DB
        if agent_role == "buyer":
            eid = state["buyer_enterprise_id"]
        else:
            eid = state["seller_enterprise_id"]

        config_result = await db_session.execute(
            select(AgentConfig).where(
                AgentConfig.enterprise_id == uuid.UUID(eid),
            ),
        )
        agent_config_model = config_result.scalar_one_or_none()
        if agent_config_model is None:
            raise HTTPException(
                status_code=422, detail=f"No agent_config for {agent_role}",
            )
        agent_config_dict = {
            "budget_ceiling": float(agent_config_model.budget_ceiling) if agent_config_model.budget_ceiling else None,
            "max_exposure": float(agent_config_model.max_exposure),
            "agent_role": agent_role,
        }

        # For accept actions, the offer_value is the last counter from the other side
        guardrail_offer = offer_value
        if action_type == "accept":
            if agent_role == "buyer":
                guardrail_offer = state.get("last_seller_offer")
            else:
                guardrail_offer = state.get("last_buyer_offer")

        action_for_guardrail = {
            "agent_role": agent_role,
            "action": action_type,
            "offer_value": guardrail_offer,
        }

        if snapshot:
            result = await guardrail_engine.enforce(
                action_envelope=action_for_guardrail,
                valuation_snapshot=snapshot,
                agent_config=agent_config_dict,
                session=state,
                session_id=session_id,
                agent_role=agent_role,
                round_num=round_num,
                db_session=db_session,
                redis_client=redis_client,
            )
            if result.status == "BLOCKED":
                if result.rule_violated == "POLICY_BREACH":
                    await self._transition_to_terminal(
                        session_id, "POLICY_BREACH", db_session, redis_client,
                    )
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": result.rule_violated,
                        "message": result.message,
                    },
                )

        # STEP 8: SANITIZE RATIONALE
        from api.middleware import sanitize_rationale
        rationale = sanitize_rationale(action.get("rationale"))

        # STEP 9: PERSIST OFFER
        offer = Offer(
            offer_id=uuid.uuid4(),
            session_id=uuid.UUID(session_id) if isinstance(session_id, str) else session_id,
            agent_role=agent_role,
            value=Decimal(str(offer_value)) if offer_value is not None else None,
            action=action_type,
            round=round_num,
            confidence=Decimal(str(action.get("confidence", 0.5))),
            strategy_tag=action.get("strategy_tag"),
            rationale=rationale,
        )
        db_session.add(offer)
        await db_session.flush()

        # STEP 10: AUDIT LOG
        await audit_logger.append(
            entity_type="negotiation",
            entity_id=session_id,
            action="OFFER_SUBMITTED",
            actor_id=eid,
            payload={
                "agent_role": agent_role,
                "action": action_type,
                "offer_value": offer_value,
                "round": round_num,
                "confidence": action.get("confidence"),
                "strategy_tag": action.get("strategy_tag"),
            },
            db_session=db_session,
        )

        # STEP 11: EVALUATE FSM TRANSITION
        new_status = state["status"]
        new_round = current_round
        is_terminal = False

        if action_type == "accept":
            def _dbg2(msg):
                with open("/tmp/compliance_debug.log", "a") as f:
                    f.write(f"{msg}\n")
            _dbg2(f"ACCEPT path entered for {str(session_id)[:8]}, agent={agent_role}")
            new_status = "AGREED"
            is_terminal = True

            # Determine final value
            if agent_role == "buyer":
                final_value = state.get("last_seller_offer") or offer_value
            else:
                final_value = state.get("last_buyer_offer") or offer_value

            await audit_logger.append(
                entity_type="negotiation",
                entity_id=session_id,
                action="SESSION_AGREED",
                actor_id=eid,
                payload={"final_agreed_value": final_value},
                db_session=db_session,
            )

            # Update status + final_agreed_value BEFORE escrow trigger
            # (EscrowManager.trigger_escrow reads neg.status from DB)
            sid_for_update = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
            await db_session.execute(
                update(Negotiation)
                .where(Negotiation.session_id == sid_for_update)
                .values(
                    status="AGREED",
                    outcome="AGREED",
                    final_agreed_value=Decimal(str(final_value)) if final_value else None,
                ),
            )
            await db_session.flush()

            _dbg2(f"About to call _trigger_escrow for {str(session_id)[:8]}")
            await self._trigger_escrow(session_id, db_session, redis_client)
            _dbg2(f"_trigger_escrow completed for {str(session_id)[:8]}")

        elif action_type == "reject":
            new_status = "WALKAWAY"
            is_terminal = True

            await audit_logger.append(
                entity_type="negotiation",
                entity_id=session_id,
                action="SESSION_WALKAWAY",
                actor_id=eid,
                payload={"agent_role": agent_role},
                db_session=db_session,
            )

        elif action_type == "counter":
            # Check ROUND_LIMIT
            next_round = current_round + 1 if state["status"] == "ROUND_LOOP" else current_round
            if next_round > state["max_rounds"]:
                new_status = "ROUND_LIMIT"
                is_terminal = True
            else:
                # Check STALL
                prev_offer_key = f"last_{agent_role}_offer"
                prev_offer = state.get(prev_offer_key)

                if prev_offer is not None and offer_value is not None:
                    delta = abs(float(offer_value) - float(prev_offer))
                    stall_count = await redis_client.update_stall_counter(
                        session_id, delta, float(prev_offer),
                    )
                    if stall_count >= 3:
                        new_status = "STALLED"
                        is_terminal = True

                if not is_terminal:
                    # Normal transition
                    if state["status"] == "BUYER_ANCHOR":
                        new_status = "SELLER_RESPONSE"
                    elif state["status"] == "SELLER_RESPONSE":
                        new_status = "ROUND_LOOP"
                        new_round = current_round + 1
                    elif state["status"] == "ROUND_LOOP":
                        new_round = current_round + 1

        if is_terminal and new_status != "AGREED":
            # Generic terminal audit
            await audit_logger.append(
                entity_type="negotiation",
                entity_id=session_id,
                action=f"SESSION_{new_status}",
                actor_id=eid,
                payload={"agent_role": agent_role, "round": round_num},
                db_session=db_session,
            )

        # STEP 12: WRITE NEW STATE
        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        update_values: dict[str, Any] = {
            "status": new_status,
            "current_round": new_round,
            "outcome": new_status if is_terminal else None,
        }
        if agent_role == "buyer" and offer_value is not None:
            update_values["last_buyer_offer"] = Decimal(str(offer_value))
        elif agent_role == "seller" and offer_value is not None:
            update_values["last_seller_offer"] = Decimal(str(offer_value))

        await db_session.execute(
            update(Negotiation).where(Negotiation.session_id == sid).values(**update_values),
        )
        await db_session.flush()

        # Update Redis
        state["status"] = new_status
        state["current_round"] = new_round
        state["last_actor"] = agent_role  # Track who just went for turn ordering
        if agent_role == "buyer" and offer_value is not None:
            state["last_buyer_offer"] = offer_value
        elif agent_role == "seller" and offer_value is not None:
            state["last_seller_offer"] = offer_value
        # Next turn: after buyer moved seller goes; after seller moved buyer goes
        state["expected_turn"] = "seller" if agent_role == "buyer" else "buyer"

        if is_terminal:
            state["outcome"] = new_status
            # Keep for 24h audit access
            await redis_client.set_session_state(
                session_id, state, 24 * 3600,
            )
        else:
            remaining = (timeout_at - datetime.now(timezone.utc)).total_seconds()
            await redis_client.set_session_state(
                session_id, state, max(int(remaining), 60),
            )

        # Reset failure count on successful action
        await redis_client.reset_failure_count(session_id, agent_role)

        # STEP 13: RETURN RESPONSE
        return {
            "session_id": session_id,
            "status": new_status,
            "current_round": new_round,
            "last_action": action_type,
            "agent_role": agent_role,
            "offer_value": offer_value,
            "timeout_at": state["timeout_at"],
            "is_terminal": is_terminal,
        }

    # ─── terminal transition ────────────────────────────────────────────
    async def _transition_to_terminal(
        self,
        session_id: str,
        terminal_state: str,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> None:
        """Generic terminal state transition."""
        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id

        await audit_logger.append(
            entity_type="negotiation",
            entity_id=str(session_id),
            action=f"SESSION_{terminal_state}",
            actor_id="system",
            payload={"terminal_state": terminal_state},
            db_session=db_session,
        )

        await db_session.execute(
            update(Negotiation)
            .where(Negotiation.session_id == sid)
            .values(status=terminal_state, outcome=terminal_state),
        )
        await db_session.flush()

        # Keep session in Redis with 24h TTL for audit
        state = await redis_client.get_session_state(str(session_id))
        if state:
            state["status"] = terminal_state
            state["outcome"] = terminal_state
            await redis_client.set_session_state(
                str(session_id), state, 24 * 3600,
            )

    # ─── escrow trigger ─────────────────────────────────────────────────
    async def _trigger_escrow(
        self, session_id: str, db_session: AsyncSession, redis_client: Any,
    ) -> None:
        """Trigger real escrow deployment via EscrowManager."""
        import logging
        import sys
        _logger = logging.getLogger("a2a_treasury")
        def _dbg(msg):
            with open("/tmp/compliance_debug.log", "a") as f:
                f.write(f"{msg}\n")
        _dbg(f"_trigger_escrow called for {str(session_id)[:8]}")
        try:
            from blockchain.escrow_manager import EscrowManager
            escrow_manager = EscrowManager()
            result = await escrow_manager.trigger_escrow(
                session_id, db_session, redis_client,
            )
            status = result.get("status", "error")
            _dbg(f"escrow result status={status} for {str(session_id)[:8]}")
            if status == "deployed":
                _logger.info("Escrow deployed for session %s", session_id)
                # ── Auto-wire compliance record ──────────────────────────
                _dbg(f"calling _auto_create_compliance for {str(session_id)[:8]}")
                await self._auto_create_compliance(session_id, db_session)
                _dbg(f"_auto_create_compliance returned for {str(session_id)[:8]}")
            elif status == "skipped":
                _logger.info(
                    "Escrow skipped for session %s: %s",
                    session_id, result.get("reason"),
                )
            else:
                _logger.warning(
                    "Escrow trigger returned %s for session %s",
                    status, session_id,
                )
        except Exception as e:
            _dbg(f"_trigger_escrow exception: {e}")
            _logger.exception("Escrow trigger failed for session %s: %s", session_id, e)
            await audit_logger.append(
                entity_type="negotiation",
                entity_id=str(session_id),
                action="ESCROW_TRIGGER_FAILED",
                actor_id="system",
                payload={"error": str(e)},
                db_session=db_session,
            )

    async def _auto_create_compliance(
        self, session_id: str, db_session: AsyncSession,
    ) -> None:
        """Auto-create compliance record when escrow deploys after AGREED."""
        import logging
        _logger = logging.getLogger("a2a_treasury")
        try:
            from db.models import ComplianceRecord as CR

            # Expire cached ORM instances so the SELECT below sees the
            # final_agreed_value written by the bulk UPDATE in process_action.
            await db_session.flush()
            db_session.expire_all()

            # Load the negotiation to get agreed value + enterprise IDs
            sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
            neg_result = await db_session.execute(
                select(Negotiation).where(Negotiation.session_id == sid),
            )
            neg = neg_result.scalar_one_or_none()
            if not neg or not neg.final_agreed_value:
                _logger.warning(
                    "Compliance auto-wire: no agreed value for %s (neg=%s, val=%s)",
                    str(session_id)[:8],
                    neg is not None,
                    getattr(neg, "final_agreed_value", None),
                )
                return

            agreed_value = float(neg.final_agreed_value)
            fx_rate = float(neg.fx_rate_locked) if neg.fx_rate_locked else 0.011
            usd_equivalent = round(agreed_value * fx_rate, 6)

            compliance = CR(
                session_id=sid,
                enterprise_id=neg.buyer_enterprise_id,
                purpose_code="P0103",
                purpose_label="Export of goods — merchandise",
                transaction_type="DOMESTIC",
                inr_amount=agreed_value,
                usdc_amount=usd_equivalent,
                usd_equivalent=usd_equivalent,
                limit_applicable=0,
                limit_utilization_pct=0,
                status="EXEMPT",
                warnings=[],
                blocking_reasons=[],
                counterparty_country="IN",
                invoice_ref=f"INV-{str(session_id)[:8].upper()}",
            )
            db_session.add(compliance)
            await db_session.flush()

            await audit_logger.append(
                entity_type="negotiation",
                entity_id=str(session_id),
                action="COMPLIANCE_RECORD_CREATED",
                actor_id="system",
                payload={
                    "purpose_code": "P0103",
                    "fema_status": "EXEMPT",
                    "usd_equivalent": usd_equivalent,
                },
                db_session=db_session,
            )
            _logger.info(
                "Compliance auto-created for session %s: EXEMPT",
                str(session_id)[:8],
            )
        except Exception as e:
            _logger.warning("Compliance auto-wire failed for %s: %s", str(session_id)[:8], e)
            import traceback
            _logger.warning("Compliance auto-wire traceback: %s", traceback.format_exc())

    # ─── helpers ────────────────────────────────────────────────────────
    def _get_expected_turn(self, state: dict) -> str:
        """Determine whose turn it is based on current FSM state."""
        status = state["status"]
        if status == "BUYER_ANCHOR":
            return "seller"  # buyer already anchored, seller responds
        elif status == "SELLER_RESPONSE":
            return "buyer"  # seller responded, buyer's turn
        elif status == "ROUND_LOOP":
            # Use last_actor to alternate turns
            last_actor = state.get("last_actor")
            if last_actor == "buyer":
                return "seller"
            elif last_actor == "seller":
                return "buyer"
            # Fallback: buyer goes first in ROUND_LOOP
            return "buyer"
        elif status == "INIT":
            return "buyer"
        return "buyer"

    async def _get_active_enterprise(
        self, enterprise_id: str, label: str, db_session: AsyncSession,
    ) -> Enterprise:
        result = await db_session.execute(
            select(Enterprise).where(
                Enterprise.enterprise_id == uuid.UUID(str(enterprise_id)),
            ),
        )
        ent = result.scalar_one_or_none()
        if ent is None:
            raise HTTPException(
                status_code=422, detail=f"{label} enterprise not found",
            )
        if ent.kyc_status != "ACTIVE":
            raise HTTPException(
                status_code=422,
                detail=f"{label} enterprise is not ACTIVE (status: {ent.kyc_status})",
            )
        return ent

    async def _get_agent_config(
        self, enterprise_id: str, label: str, db_session: AsyncSession,
    ) -> AgentConfig:
        result = await db_session.execute(
            select(AgentConfig).where(
                AgentConfig.enterprise_id == uuid.UUID(str(enterprise_id)),
            ),
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise HTTPException(
                status_code=422,
                detail=f"{label} enterprise has no agent_config",
            )
        return config

    async def _get_treasury_policy(
        self, enterprise_id: str, label: str, db_session: AsyncSession,
    ) -> TreasuryPolicy:
        result = await db_session.execute(
            select(TreasuryPolicy).where(
                TreasuryPolicy.enterprise_id == uuid.UUID(str(enterprise_id)),
                TreasuryPolicy.active == True,
            ),
        )
        policy = result.scalar_one_or_none()
        if policy is None:
            raise HTTPException(
                status_code=422,
                detail=f"{label} enterprise has no active treasury_policy",
            )
        return policy

    @staticmethod
    def _config_to_dict(config: AgentConfig, role_override: str) -> dict:
        """Convert ORM AgentConfig to plain dict for valuation layer."""
        return {
            "intrinsic_value": float(config.intrinsic_value),
            "risk_factor": float(config.risk_factor),
            "negotiation_margin": float(config.negotiation_margin),
            "concession_curve": config.concession_curve,
            "budget_ceiling": float(config.budget_ceiling) if config.budget_ceiling else None,
            "max_exposure": float(config.max_exposure),
            "agent_role": role_override,
        }
