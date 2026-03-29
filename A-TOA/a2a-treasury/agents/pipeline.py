"""
agents/pipeline.py — Shared 4-layer agent turn pipeline.

Layer 1 → Layer 2 → Layer 3 → Layer 4 → submit via A2ATaskManager.
Used by both BuyerAgent and SellerAgent. No direct agent-to-agent communication.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.flexibility_tracker import FlexibilityTracker
from core.guardrails import GuardrailEngine
from core.llm_reasoning import LLMAdvisory, GeminiAdvisor
from core.strategy import (
    compute_next_offer,
    compute_opening_offer,
    should_accept,
    should_reject,
)
from db.models import AgentConfig, Offer


guardrail_engine = GuardrailEngine()
flexibility_tracker = FlexibilityTracker()
gemini_advisor = GeminiAdvisor()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_offer_history(session_id: str, db_session: Any) -> list[dict]:
    """Load offer history for session (for LLM). No financial thresholds."""
    result = await db_session.execute(
        select(Offer)
        .where(Offer.session_id == uuid.UUID(session_id))
        .order_by(Offer.timestamp.asc()),
    )
    offers = result.scalars().all()
    return [
        {
            "round": o.round,
            "agent_role": o.agent_role,
            "value": float(o.value) if o.value is not None else None,
            "action": o.action,
        }
        for o in offers
    ]


async def _load_agent_config_dict(
    enterprise_id: str,
    agent_role: str,
    db_session: Any,
) -> dict:
    """Load agent config as dict for strategy/guardrails."""
    result = await db_session.execute(
        select(AgentConfig).where(
            AgentConfig.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    config = result.scalar_one_or_none()
    if not config:
        raise RuntimeError(f"No agent_config for {agent_role} enterprise {enterprise_id}")
    return {
        "intrinsic_value": float(config.intrinsic_value),
        "risk_factor": float(config.risk_factor),
        "negotiation_margin": float(config.negotiation_margin),
        "concession_curve": config.concession_curve or {},
        "budget_ceiling": float(config.budget_ceiling) if config.budget_ceiling else None,
        "max_exposure": float(config.max_exposure),
        "agent_role": agent_role,
    }


async def run_agent_turn(
    session_id: str,
    agent_role: str,
    current_round: int,
    session_state: dict,
    agent_config: dict,
    db_session: Any,
    redis_client: Any,
    task_manager: Any,
) -> dict:
    """
    Execute one full agent turn through all 4 layers.
    Returns the result from task_manager.route_offer (or raises).
    """
    max_rounds = session_state.get("max_rounds", 8)
    rounds_remaining = max(0, max_rounds - current_round)
    last_own_offer = (
        session_state.get("last_buyer_offer")
        if agent_role == "buyer"
        else session_state.get("last_seller_offer")
    )
    last_opponent_offer = (
        session_state.get("last_seller_offer")
        if agent_role == "buyer"
        else session_state.get("last_buyer_offer")
    )

    # Prev opponent offer (for tit-for-tat / flexibility) — from DB
    prev_opponent_offer = None
    if last_opponent_offer is not None:
        result = await db_session.execute(
            select(Offer)
            .where(
                Offer.session_id == uuid.UUID(session_id),
                Offer.agent_role == ("seller" if agent_role == "buyer" else "buyer"),
            )
            .order_by(Offer.timestamp.desc())
            .limit(2),
        )
        opp_offers = result.scalars().all()
        if len(opp_offers) >= 2:
            prev_opponent_offer = float(opp_offers[1].value) if opp_offers[1].value else None

    # STEP 1 — Valuation snapshot (frozen at session creation)
    snapshot_key = f"{session_id}:{agent_role}"
    snapshot = await redis_client.get_valuation_snapshot(snapshot_key)
    if not snapshot:
        raise RuntimeError("Valuation snapshot missing")

    # STEP 2 — Flexibility metrics (update after observing opponent move)
    if last_opponent_offer is not None and prev_opponent_offer is not None:
        await flexibility_tracker.update(
            session_id=session_id,
            observing_role=agent_role,
            opponent_offer=last_opponent_offer,
            prev_opponent_offer=prev_opponent_offer,
            round_num=current_round,
            response_time_seconds=1.0,
            redis_client=redis_client,
        )
    flex_metrics = await flexibility_tracker.get(
        session_id, agent_role, redis_client
    )
    flexibility_score = flex_metrics.get("flexibility_score", 0.5)

    # STEP 3 — LLM Advisory (Layer 3)
    llm_modifier = 0.0
    offer_history = await _load_offer_history(session_id, db_session)
    session_metadata = {
        "current_round": current_round,
        "max_rounds": max_rounds,
        "agent_role": agent_role,
    }
    llm_advisory: LLMAdvisory = await gemini_advisor.classify_opponent(
        offer_history, session_metadata, flex_metrics, session_id,
        db_session=db_session,
    )
    llm_modifier = llm_advisory.recommended_modifier

    # STEP 4 — Strategy decision (Layer 2)
    action = "counter"
    offer_value = None
    strategy_tag = "concede"
    confidence = 0.5
    rationale = ""

    if current_round == 1 and last_own_offer is None:
        # Opening offer (buyer already has opening in state from create_session; seller computes)
        strategy_result = compute_opening_offer(
            snapshot, agent_config, agent_role
        )
        action = "counter"
        offer_value = strategy_result["offer_value"]
        strategy_tag = strategy_result["strategy_tag"]
        confidence = strategy_result["confidence"]
        rationale = strategy_result.get("rationale", "")
    else:
        # Check accept
        if last_opponent_offer is not None:
            if should_accept(
                last_opponent_offer,
                snapshot,
                current_round,
                max_rounds,
                flexibility_score,
            ):
                action = "accept"
                offer_value = None
                strategy_tag = "concede"
                confidence = 0.95
                rationale = "Accept within bounds"
            elif should_reject(
                last_opponent_offer,
                snapshot,
                current_round,
                await redis_client.get_failure_count(session_id, agent_role),
            ):
                action = "reject"
                offer_value = None
                strategy_tag = "hold"
                confidence = 0.60
                rationale = "Reject"
            else:
                # Counter
                strategy_result = compute_next_offer(
                    current_round=current_round,
                    last_own_offer=last_own_offer or snapshot["opening_anchor"],
                    last_opponent_offer=last_opponent_offer,
                    prev_opponent_offer=prev_opponent_offer,
                    valuation_snapshot=snapshot,
                    agent_config=agent_config,
                    flexibility_score=flexibility_score,
                    llm_modifier=llm_modifier,
                    agent_role=agent_role,
                    rounds_remaining=rounds_remaining,
                )
                action = "counter"
                offer_value = strategy_result["offer_value"]
                strategy_tag = strategy_result["strategy_tag"]
                confidence = strategy_result["confidence"]
                rationale = strategy_result.get("rationale", "")
        else:
            # No opponent offer yet (shouldn't happen for seller round 1)
            strategy_result = compute_opening_offer(
                snapshot, agent_config, agent_role
            )
            action = "counter"
            offer_value = strategy_result["offer_value"]
            strategy_tag = strategy_result["strategy_tag"]
            confidence = strategy_result["confidence"]
            rationale = strategy_result.get("rationale", "")

    # STEP 5 — Build envelope
    envelope = {
        "session_id": session_id,
        "agent_role": agent_role,
        "round": current_round,
        "action": action,
        "offer_value": offer_value,
        "confidence": confidence,
        "strategy_tag": strategy_tag,
        "rationale": rationale,
        "timestamp": _utc_now_iso(),
    }

    # STEP 6 — Guardrail (Layer 4)
    guardrail_result = await guardrail_engine.enforce(
        envelope,
        snapshot,
        agent_config,
        session_state,
        session_id,
        agent_role,
        current_round,
        db_session,
        redis_client,
    )
    if guardrail_result.status == "BLOCKED":
        if guardrail_result.rule_violated == "POLICY_BREACH":
            # Signal handled by state machine on next process_action
            pass
        raise RuntimeError(
            f"Guardrail blocked: {guardrail_result.rule_violated} — {guardrail_result.message}"
        )

    # STEP 7 — Route via A2A Task Manager
    task = await task_manager.route_offer(
        session_id,
        envelope,
        agent_role,
        redis_client,
        db_session,
    )
    return {"task_id": task.task_id, "status": task.status.value, "payload": task.payload}
