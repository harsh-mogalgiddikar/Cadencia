"""
api/routes/sessions.py — Session lifecycle API endpoints.

POST /sessions                       — create session
POST /sessions/{id}/action           — submit agent action
GET  /sessions/{id}/status           — session status
GET  /sessions/{id}/offers           — offer history (no rationale)
GET  /sessions/{id}/transcript       — audit transcript
GET  /sessions/                      — list sessions
"""
from __future__ import annotations

import os
import time
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import UserContext, require_admin, require_any_role
from api.schemas.session import (
    ActionResponse,
    AgentActionEnvelope,
    CreateSessionRequest,
    CreateSessionResponse,
    OfferDetail,
    OfferListResponse,
    SessionListResponse,
    SessionStatusResponse,
)
from core.state_machine import DANPStateMachine
from db.audit_logger import AuditLogger
from db.database import get_db
from db.models import AgentConfig, Enterprise, Negotiation, Offer
from framework import FrameworkRegistry
from framework.interfaces import check_agent_compatibility
from framework.policy.acf_policy_engine import ACFPolicyEngine

router = APIRouter(prefix="/sessions", tags=["Sessions"])
state_machine = DANPStateMachine()
audit_logger = AuditLogger()
policy_engine = ACFPolicyEngine()

COMPLIANCE_STRICT_MODE = os.getenv("COMPLIANCE_STRICT_MODE", "false").lower() == "true"


def _get_redis():
    from api.main import redis_manager
    return redis_manager


async def _lock_fx_and_compliance_for_session(
    session_id: str,
    buyer_id: str,
    seller_id: str,
    opening_offer_value: float,
    db: AsyncSession,
    redis,
):
    """
    Phase 4: Lock FX rate for session, run FEMA compliance, record and update negotiation.
    On compliance engine error: log warning, set status=EXEMPT, proceed (never block).
    Returns the FEMACheckResult or None if compliance check failed.
    """
    from core.fx_engine import fx_engine
    from compliance.fema_engine import fema_engine, FEMAComplianceStatus

    try:
        quote = await fx_engine.lock_rate_for_session(session_id, redis, db)
    except Exception as e:
        import logging
        logging.getLogger("a2a_treasury.sessions").warning(
            "FX lock failed for session %s: %s", session_id[:8], e
        )
        return None

    usdc_equivalent = fx_engine.convert_inr_to_usdc(opening_offer_value, quote).usdc_amount

    await db.execute(
        update(Negotiation)
        .where(Negotiation.session_id == uuid.UUID(session_id))
        .values(
            fx_quote_id=uuid.UUID(quote.quote_id),
            fx_rate_locked=Decimal(str(quote.sell_rate)),
            usdc_equivalent=Decimal(str(usdc_equivalent)),
        )
    )
    await db.flush()

    await audit_logger.append(
        entity_type="negotiation",
        entity_id=session_id,
        action="FX_RATE_LOCKED",
        actor_id=buyer_id,
        payload={
            "quote_id": quote.quote_id,
            "sell_rate": quote.sell_rate,
            "usdc_equivalent": usdc_equivalent,
            "source": quote.source,
        },
        db_session=db,
    )

    try:
        result = await fema_engine.check_session_compliance(
            session_id=session_id,
            buyer_enterprise_id=buyer_id,
            seller_enterprise_id=seller_id,
            inr_amount=opening_offer_value,
            usdc_amount=usdc_equivalent,
            db_session=db,
        )
    except Exception as e:
        import logging
        logging.getLogger("a2a_treasury.sessions").warning(
            "Compliance check failed for session %s: %s — setting EXEMPT", session_id[:8], e
        )
        result = None

    if result:
        await fema_engine.record_compliance(
            session_id, buyer_id, result, db
        )
        await db.execute(
            update(Negotiation)
            .where(Negotiation.session_id == uuid.UUID(session_id))
            .values(compliance_status=result.status.value)
        )
        await db.flush()
        await audit_logger.append(
            entity_type="negotiation",
            entity_id=session_id,
            action="COMPLIANCE_CHECKED",
            actor_id="system",
            payload={
                "status": result.status.value,
                "purpose_code": result.purpose_code,
                "transaction_type": result.transaction_type,
            },
            db_session=db,
        )
    return result


# ─── POST /sessions ────────────────────────────────────────────────────────
@router.post("/", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only — create a new negotiation session. Phase 4: FX lock + compliance auto-wired."""
    redis = _get_redis()
    allowed = await redis.check_session_rate_limit(str(admin.enterprise_id))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "limit": "10 sessions per hour per enterprise",
                "retry_after": 3600 - (int(time.time()) % 3600),
            },
        )
    result = await state_machine.create_session(
        buyer_enterprise_id=admin.enterprise_id,
        seller_enterprise_id=body.seller_enterprise_id,
        initial_offer_value=body.initial_offer_value,
        milestone_template_id=body.milestone_template_id,
        timeout_seconds=body.timeout_seconds,
        max_rounds=body.max_rounds,
        db_session=db,
        redis_client=redis,
    )
    session_id = result["session_id"]
    buyer_id = str(admin.enterprise_id)
    seller_id = body.seller_enterprise_id
    opening_offer_value = body.initial_offer_value

    compliance_result = await _lock_fx_and_compliance_for_session(
        session_id, buyer_id, seller_id, opening_offer_value, db, redis,
    )

    from compliance.fema_engine import FEMAComplianceStatus
    if COMPLIANCE_STRICT_MODE and compliance_result and compliance_result.status == FEMAComplianceStatus.NON_COMPLIANT:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "error": "COMPLIANCE_BLOCKED",
                "reasons": compliance_result.blocking_reasons,
                "purpose_code": compliance_result.purpose_code,
            },
        )

    await db.commit()
    return CreateSessionResponse(**result)


# ─── POST /sessions/{id}/action ────────────────────────────────────────────
@router.post("/{session_id}/action", response_model=ActionResponse)
async def submit_action(
    session_id: str,
    body: AgentActionEnvelope,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Submit an agent action to the state machine."""
    # Ensure session_id matches
    if body.session_id != session_id:
        raise HTTPException(422, "session_id in path and body must match")

    redis = _get_redis()
    action_dict = body.model_dump()
    result = await state_machine.process_action(
        action=action_dict,
        db_session=db,
        redis_client=redis,
    )
    return ActionResponse(**result)


# ─── GET /sessions/{id}/status ──────────────────────────────────────────────
@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Get current session status."""
    result = await db.execute(
        select(Negotiation).where(
            Negotiation.session_id == uuid.UUID(session_id),
        ),
    )
    neg = result.scalar_one_or_none()
    if neg is None:
        raise HTTPException(404, "Session not found")

    from core.state_machine import TERMINAL_STATES

    expected_turn = None
    if neg.status not in TERMINAL_STATES:
        offer_result = await db.execute(
            select(Offer)
            .where(Offer.session_id == neg.session_id)
            .order_by(Offer.timestamp.desc())
            .limit(1),
        )
        last_offer = offer_result.scalar_one_or_none()
        if last_offer is None:
            expected_turn = "buyer"
        elif last_offer.agent_role == "buyer":
            expected_turn = "seller"
        else:
            expected_turn = "buyer"

    return SessionStatusResponse(
        session_id=str(neg.session_id),
        status=neg.status,
        current_round=neg.current_round,
        max_rounds=neg.max_rounds,
        timeout_at=neg.timeout_at.isoformat(),
        is_terminal=neg.status in TERMINAL_STATES,
        outcome=neg.outcome,
        final_agreed_value=float(neg.final_agreed_value) if neg.final_agreed_value else None,
        expected_turn=expected_turn,
    )


# ─── GET /sessions/{id}/offers ──────────────────────────────────────────────
@router.get("/{session_id}/offers", response_model=OfferListResponse)
async def get_session_offers(
    session_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Get all offers for a session. Rationale is NEVER included."""
    result = await db.execute(
        select(Offer)
        .where(Offer.session_id == uuid.UUID(session_id))
        .order_by(Offer.timestamp.asc()),
    )
    offers = result.scalars().all()

    return OfferListResponse(
        session_id=session_id,
        offers=[
            OfferDetail(
                offer_id=str(o.offer_id),
                agent_role=o.agent_role,
                value=float(o.value) if o.value else None,
                action=o.action,
                round=o.round,
                confidence=float(o.confidence) if o.confidence else None,
                strategy_tag=o.strategy_tag,
                timestamp=o.timestamp.isoformat() if o.timestamp else "",
            )
            for o in offers
        ],
    )


# ─── GET /sessions/{id}/transcript ──────────────────────────────────────────
@router.get("/{session_id}/transcript")
async def get_session_transcript(
    session_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Get cryptographically-verified audit transcript for a session."""
    return await audit_logger.export_session_transcript(session_id, db)


# ─── POST /sessions/{session_id}/run ────────────────────────────────────────
@router.post("/{session_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_autonomous_negotiation(
    session_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Start autonomous negotiation (NeutralProtocolEngine.run_negotiation) in background.
    Returns 202 immediately. Poll GET /sessions/{id}/status for progress.
    """
    import asyncio
    from agents.neutral_agent import NeutralProtocolEngine
    from db.database import get_session_factory

    redis = _get_redis()
    result = await db.execute(
        select(Negotiation).where(
            Negotiation.session_id == uuid.UUID(session_id),
        ),
    )
    neg = result.scalar_one_or_none()
    if neg is None:
        raise HTTPException(404, "Session not found")

    # Framework-level compatibility check between buyer and seller agents
    ent_result = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id.in_(
                [neg.buyer_enterprise_id, neg.seller_enterprise_id],
            ),
        ),
    )
    enterprises = {str(e.enterprise_id): e for e in ent_result.scalars().all()}
    buyer_ent = enterprises.get(str(neg.buyer_enterprise_id))
    seller_ent = enterprises.get(str(neg.seller_enterprise_id))
    if not buyer_ent or not seller_ent:
        raise HTTPException(404, "Buyer or seller enterprise not found")

    # Phase 2: Check for valid unexpired capability handshake
    from datetime import datetime, timezone as tz
    from db.models import CapabilityHandshake
    handshake_used = False
    protocol_id = None
    try:
        hs_result = await db.execute(
            select(CapabilityHandshake)
            .where(
                CapabilityHandshake.buyer_enterprise_id == neg.buyer_enterprise_id,
                CapabilityHandshake.seller_enterprise_id == neg.seller_enterprise_id,
                CapabilityHandshake.compatible == True,
                CapabilityHandshake.expires_at > datetime.now(tz.utc),
            )
            .order_by(CapabilityHandshake.created_at.desc())
            .limit(1)
        )
        handshake = hs_result.scalar_one_or_none()
        if handshake and handshake.selected_protocol:
            protocol_id = handshake.selected_protocol
            handshake_used = True
            import logging
            logging.getLogger("a2a_treasury.sessions").info(
                "Using handshake %s protocol=%s for session %s",
                str(handshake.handshake_id)[:8], protocol_id, session_id[:8],
            )
    except Exception:
        pass  # fall through to existing compatibility check

    if not handshake_used:
        # Use stored agent cards if available; otherwise, fall back to minimal cards
        buyer_card = buyer_ent.agent_card_data or {
            "protocols": [{"id": "DANP-v1"}],
            "settlement_networks": ["algorand-testnet"],
            "payment_methods": ["x402"],
        }
        seller_card = seller_ent.agent_card_data or {
            "protocols": [{"id": "DANP-v1"}],
            "settlement_networks": ["algorand-testnet"],
            "payment_methods": ["x402"],
        }

        compatibility = check_agent_compatibility(buyer_card, seller_card)
        if not compatibility["compatible"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INCOMPATIBLE_AGENTS",
                    "reasons": compatibility["incompatibility_reasons"],
                    "buyer_protocols": [p.get("id") for p in buyer_card.get("protocols", [])],
                    "seller_protocols": [p.get("id") for p in seller_card.get("protocols", [])],
                },
            )

        shared_protocols = compatibility["shared_protocols"]
        protocol_id = shared_protocols[0] if shared_protocols else "DANP-v1"

    protocol = FrameworkRegistry.get_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(
            status_code=500,
            detail=f"Negotiation protocol not registered: {protocol_id}",
        )

    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as db_session:
            try:
                # Call through the framework protocol wrapper for bookkeeping.
                current_state = await redis.get_session_state(session_id)
                if current_state:
                    # TODO: Phase 2 — use evaluation result to influence orchestration flow.
                    protocol.evaluate(session_id, current_state)

                engine = NeutralProtocolEngine()
                await engine.run_negotiation(session_id, db_session, redis)
            except Exception:
                # Errors are already logged inside the engine/state machine.
                pass

    asyncio.create_task(_run())

    return {
        "session_id": session_id,
        "status": "RUNNING",
        "message": "Autonomous negotiation started",
    }


# ─── GET /sessions/ ─────────────────────────────────────────────────────────
@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    enterprise_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only — paginated list of sessions."""
    from core.state_machine import TERMINAL_STATES

    query = select(Negotiation)
    count_query = select(func.count(Negotiation.session_id))

    if enterprise_id:
        eid = uuid.UUID(enterprise_id)
        query = query.where(
            (Negotiation.buyer_enterprise_id == eid)
            | (Negotiation.seller_enterprise_id == eid),
        )
        count_query = count_query.where(
            (Negotiation.buyer_enterprise_id == eid)
            | (Negotiation.seller_enterprise_id == eid),
        )

    if status_filter:
        query = query.where(Negotiation.status == status_filter)
        count_query = count_query.where(Negotiation.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size

    result = await db.execute(
        query.order_by(Negotiation.initiated_at.desc())
        .offset(offset)
        .limit(page_size),
    )
    sessions = result.scalars().all()

    return SessionListResponse(
        items=[
            SessionStatusResponse(
                session_id=str(s.session_id),
                status=s.status,
                current_round=s.current_round,
                max_rounds=s.max_rounds,
                timeout_at=s.timeout_at.isoformat(),
                is_terminal=s.status in TERMINAL_STATES,
                outcome=s.outcome,
                final_agreed_value=float(s.final_agreed_value) if s.final_agreed_value else None,
            )
            for s in sessions
        ],
        total=total,
        page=page,
    )


# ─── POST /sessions/multi ──────────────────────────────────────────────────
class MultiSessionRequest(BaseModel):
    seller_enterprise_ids: list[str]
    initial_offer_value: float
    timeout_seconds: int = 3600


@router.post("/multi", status_code=status.HTTP_202_ACCEPTED)
async def create_multi_session(
    body: MultiSessionRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a multi-party negotiation: one buyer vs multiple sellers.
    Each seller gets a child DANP session. Returns 202 immediately.
    """
    from agents.multi_party_session import multi_party_coordinator
    from fastapi import BackgroundTasks

    redis = _get_redis()

    result = await multi_party_coordinator.create_multi_session(
        buyer_enterprise_id=str(admin.enterprise_id),
        seller_enterprise_ids=body.seller_enterprise_ids,
        initial_offer_value=body.initial_offer_value,
        timeout_seconds=body.timeout_seconds,
        db_session=db,
        redis_client=redis,
    )

    # Phase 4: FX lock + compliance for each child session
    for i, session_id in enumerate(result["child_session_ids"]):
        seller_id = body.seller_enterprise_ids[i]
        await _lock_fx_and_compliance_for_session(
            session_id,
            str(admin.enterprise_id),
            seller_id,
            body.initial_offer_value,
            db,
            redis,
        )

    await db.commit()

    # Run in background
    import asyncio
    async def _run_multi():
        from db.database import async_session_factory
        async with async_session_factory() as bg_db:
            await multi_party_coordinator.run_multi_session(
                result["multi_session_id"], bg_db, redis,
            )
            await bg_db.commit()

    asyncio.create_task(_run_multi())

    return {
        "multi_session_id": result["multi_session_id"],
        "child_session_ids": result["child_session_ids"],
        "status": "ACTIVE",
        "seller_count": len(body.seller_enterprise_ids),
    }


@router.get("/multi/{multi_session_id}")
async def get_multi_session_status(
    multi_session_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Returns multi-party session status."""
    from agents.multi_party_session import multi_party_coordinator
    return await multi_party_coordinator.get_multi_session_status(
        multi_session_id, db
    )


@router.get("/multi/{multi_session_id}/leaderboard")
async def get_multi_session_leaderboard(
    multi_session_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Ranked seller offers for a multi-party session."""
    from agents.multi_party_session import multi_party_coordinator
    return await multi_party_coordinator.get_leaderboard(
        multi_session_id, db
    )
