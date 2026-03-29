"""
api/routes/handshake.py — Capability Negotiation Handshake endpoints.

POST /handshake              — run compatibility check, store handshake
GET  /handshake/{id}         — retrieve stored handshake
GET  /handshake/session/{id} — get handshake for a session
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from db.audit_logger import AuditLogger
from db.database import get_db
from db.models import CapabilityHandshake, Enterprise
from framework.interfaces import check_agent_compatibility

router = APIRouter(prefix="/handshake", tags=["Handshake"])
audit_logger = AuditLogger()

HANDSHAKE_TTL_MINUTES = 30

# ─── Fallback agent card ────────────────────────────────────────────────────
_FALLBACK_CARD = {
    "protocols": [{"id": "DANP-v1"}],
    "settlement_networks": ["algorand-testnet"],
    "payment_methods": ["x402"],
}


# ─── Request / Response schemas ─────────────────────────────────────────────
class HandshakeRequest(BaseModel):
    buyer_enterprise_id: str
    seller_enterprise_id: str
    session_id: str | None = None


# ─── POST /handshake ────────────────────────────────────────────────────────
@router.post("/")
async def create_handshake(
    body: HandshakeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run capability compatibility check between buyer and seller agents.
    Returns 200 if compatible, 409 if not compatible.
    """
    # 1. Load buyer enterprise
    try:
        buyer_uuid = uuid.UUID(body.buyer_enterprise_id)
    except ValueError:
        raise HTTPException(400, "Invalid buyer_enterprise_id format")

    buyer_result = await db.execute(
        select(Enterprise).where(Enterprise.enterprise_id == buyer_uuid)
    )
    buyer = buyer_result.scalar_one_or_none()
    if not buyer:
        raise HTTPException(404, "Buyer enterprise not found")

    # 2. Load seller enterprise
    try:
        seller_uuid = uuid.UUID(body.seller_enterprise_id)
    except ValueError:
        raise HTTPException(400, "Invalid seller_enterprise_id format")

    seller_result = await db.execute(
        select(Enterprise).where(Enterprise.enterprise_id == seller_uuid)
    )
    seller = seller_result.scalar_one_or_none()
    if not seller:
        raise HTTPException(404, "Seller enterprise not found")

    # 3-4. Load agent cards (with fallback)
    buyer_card = buyer.agent_card_data or _FALLBACK_CARD.copy()
    seller_card = seller.agent_card_data or _FALLBACK_CARD.copy()

    # 5. Check compatibility
    compatibility = check_agent_compatibility(buyer_card, seller_card)

    # 6. Selected protocol
    shared_protocols = compatibility["shared_protocols"]
    selected_protocol = shared_protocols[0] if shared_protocols else None

    # 7. Selected settlement
    shared_networks = compatibility["shared_settlement_networks"]
    shared_payments = compatibility["shared_payment_methods"]
    selected_settlement = None
    if shared_payments and shared_networks:
        selected_settlement = f"{shared_payments[0]}-{shared_networks[0]}"

    # 8. Expiry
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=HANDSHAKE_TTL_MINUTES)

    # 9. Parse optional session_id
    session_uuid = None
    if body.session_id:
        try:
            session_uuid = uuid.UUID(body.session_id)
        except ValueError:
            pass

    # 10. Save to DB
    handshake = CapabilityHandshake(
        buyer_enterprise_id=buyer_uuid,
        seller_enterprise_id=seller_uuid,
        session_id=session_uuid,
        compatible=compatibility["compatible"],
        shared_protocols=shared_protocols,
        shared_settlement_networks=shared_networks,
        shared_payment_methods=shared_payments,
        incompatibility_reasons=compatibility["incompatibility_reasons"],
        buyer_card_snapshot=buyer_card,
        seller_card_snapshot=seller_card,
        selected_protocol=selected_protocol,
        selected_settlement=selected_settlement,
        expires_at=expires_at,
    )
    db.add(handshake)
    await db.flush()

    # 11. Audit log
    await audit_logger.append(
        entity_type="handshake",
        entity_id=str(handshake.handshake_id),
        action="CAPABILITY_HANDSHAKE",
        actor_id=str(buyer_uuid),
        payload={
            "buyer_enterprise_id": str(buyer_uuid),
            "seller_enterprise_id": str(seller_uuid),
            "compatible": compatibility["compatible"],
            "selected_protocol": selected_protocol,
            "selected_settlement": selected_settlement,
            "shared_protocols": shared_protocols,
            "session_id": str(session_uuid) if session_uuid else None,
        },
        db_session=db,
    )

    await db.commit()

    response_body = {
        "handshake_id": str(handshake.handshake_id),
        "compatible": compatibility["compatible"],
        "selected_protocol": selected_protocol,
        "selected_settlement": selected_settlement,
        "shared_protocols": shared_protocols,
        "shared_settlement_networks": shared_networks,
        "shared_payment_methods": shared_payments,
        "incompatibility_reasons": compatibility["incompatibility_reasons"],
        "expires_at": expires_at.isoformat(),
        "buyer_enterprise_id": str(buyer_uuid),
        "seller_enterprise_id": str(seller_uuid),
    }

    if compatibility["compatible"]:
        response_body["message"] = "Agents are compatible. Proceed to negotiation."
        return response_body
    else:
        response_body["message"] = "Agents are not compatible. Negotiation cannot proceed."
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content=response_body)


# ─── GET /handshake/{handshake_id} ──────────────────────────────────────────
@router.get("/{handshake_id}")
async def get_handshake(
    handshake_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve stored handshake record by ID. 404 if not found."""
    try:
        hid = uuid.UUID(handshake_id)
    except ValueError:
        raise HTTPException(400, "Invalid handshake_id format")

    result = await db.execute(
        select(CapabilityHandshake).where(CapabilityHandshake.handshake_id == hid)
    )
    hs = result.scalar_one_or_none()
    if not hs:
        raise HTTPException(404, "Handshake not found")

    now = datetime.now(timezone.utc)
    expired = hs.expires_at < now if hs.expires_at else False

    return {
        "handshake_id": str(hs.handshake_id),
        "compatible": hs.compatible,
        "selected_protocol": hs.selected_protocol,
        "selected_settlement": hs.selected_settlement,
        "shared_protocols": hs.shared_protocols or [],
        "shared_settlement_networks": hs.shared_settlement_networks or [],
        "shared_payment_methods": hs.shared_payment_methods or [],
        "incompatibility_reasons": hs.incompatibility_reasons or [],
        "expires_at": hs.expires_at.isoformat() if hs.expires_at else None,
        "created_at": hs.created_at.isoformat() if hs.created_at else None,
        "expired": expired,
        "buyer_enterprise_id": str(hs.buyer_enterprise_id),
        "seller_enterprise_id": str(hs.seller_enterprise_id),
        "message": "Agents are compatible. Proceed to negotiation." if hs.compatible
                   else "Agents are not compatible. Negotiation cannot proceed.",
    }


# ─── GET /handshake/session/{session_id} ────────────────────────────────────
@router.get("/session/{session_id}")
async def get_handshake_by_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns the most recent handshake for a given session_id. 404 if none found."""
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(400, "Invalid session_id format")

    result = await db.execute(
        select(CapabilityHandshake)
        .where(CapabilityHandshake.session_id == sid)
        .order_by(CapabilityHandshake.created_at.desc())
        .limit(1)
    )
    hs = result.scalar_one_or_none()
    if not hs:
        raise HTTPException(404, "No handshake found for this session")

    now = datetime.now(timezone.utc)
    expired = hs.expires_at < now if hs.expires_at else False

    return {
        "handshake_id": str(hs.handshake_id),
        "compatible": hs.compatible,
        "selected_protocol": hs.selected_protocol,
        "selected_settlement": hs.selected_settlement,
        "shared_protocols": hs.shared_protocols or [],
        "shared_settlement_networks": hs.shared_settlement_networks or [],
        "shared_payment_methods": hs.shared_payment_methods or [],
        "incompatibility_reasons": hs.incompatibility_reasons or [],
        "expires_at": hs.expires_at.isoformat() if hs.expires_at else None,
        "created_at": hs.created_at.isoformat() if hs.created_at else None,
        "expired": expired,
        "buyer_enterprise_id": str(hs.buyer_enterprise_id),
        "seller_enterprise_id": str(hs.seller_enterprise_id),
        "session_id": str(hs.session_id) if hs.session_id else None,
    }
