"""
api/routes/deliver.py — x402 delivery endpoint.

POST /v1/deliver/{session_id}
  - First call (no X-PAYMENT): returns HTTP 402 with x402 payment requirements
  - Second call (with X-PAYMENT): verifies payment, records delivery, returns 200

This is the x402 protocol contract: 402 → sign → retry with header → 200.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import UserContext, require_any_role
from core.x402_handler import x402_handler
from db.audit_logger import AuditLogger
from db.database import get_db
from db.models import Delivery, EscrowContract, Negotiation
from framework import FrameworkRegistry

router = APIRouter(prefix="/deliver", tags=["x402-delivery"])
audit_logger = AuditLogger()


@router.post("/{session_id}")
async def deliver(
    session_id: str,
    request: Request,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """
    x402 delivery endpoint.
    First call → 402 with payment requirements.
    Second call with X-PAYMENT header → verify + 200.
    """
    # ── STEP 1 — Load and validate session ──────────────────────────
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    result = await db.execute(
        select(Negotiation).where(Negotiation.session_id == sid)
    )
    neg = result.scalar_one_or_none()
    if not neg:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    if neg.status != "AGREED":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "SESSION_NOT_AGREED",
                "current_status": neg.status,
            },
        )

    # ── STEP 2 — Idempotency check ─────────────────────────────────
    existing = await db.execute(
        select(Delivery).where(Delivery.session_id == sid)
    )
    delivery = existing.scalar_one_or_none()
    if delivery:
        return JSONResponse(
            status_code=200,
            content={
                "delivered": True,
                "session_id": session_id,
                "payment_tx_id": delivery.tx_id,
                "network": delivery.network,
                "amount_usdc": float(delivery.amount_usdc),
                "x402_verified": True,
                "idempotent": True,
            },
        )

    # ── STEP 3 — Get escrow address ─────────────────────────────────
    escrow_result = await db.execute(
        select(EscrowContract)
        .where(EscrowContract.session_id == sid)
        .order_by(EscrowContract.deployed_at.desc())
        .limit(1)
    )
    escrow_rec = escrow_result.scalar_one_or_none()
    escrow_address = escrow_rec.contract_ref if escrow_rec else "SIM-ESCROW-ADDRESS"

    # In LIVE mode, use the real seller wallet as payment destination
    # (escrow addresses are simulated and don't exist on-chain)
    import os
    seller_wallet = os.environ.get("SELLER_WALLET_ADDRESS", "")
    if not x402_handler.simulation_mode and seller_wallet:
        pay_to_address = seller_wallet
    else:
        pay_to_address = escrow_address

    # Compute USDC amount
    amount_usdc = float(neg.usdc_equivalent or 0)
    if amount_usdc == 0 and neg.final_agreed_value:
        fx_rate = float(neg.fx_rate_locked or 0.01100681)
        amount_usdc = float(neg.final_agreed_value) * fx_rate

    inr_amount = float(neg.final_agreed_value or 0)
    fx_rate = float(neg.fx_rate_locked or 0)

    # ── STEP 4 — Check X-PAYMENT header ─────────────────────────────
    x_payment = request.headers.get("X-PAYMENT")

    if not x_payment:
        # Return HTTP 402 — this IS the x402 protocol trigger
        provider = FrameworkRegistry.get_settlement_provider("x402-algorand-testnet")
        if provider is None:
            # Fallback to direct handler if registry not initialized
            response_402 = x402_handler.build_402_response(
                session_id=session_id,
                amount_usdc=amount_usdc,
                escrow_address=pay_to_address,
                inr_amount=inr_amount,
                fx_rate=fx_rate,
            )
        else:
            meta = {
                "inr_amount": inr_amount,
                "fx_rate": fx_rate,
                "escrow_address": pay_to_address,
            }
            envelope = provider.request_payment(
                session_id=session_id,
                amount=amount_usdc,
                currency="USDC",
                buyer_address="",
                seller_address=pay_to_address,
                metadata=meta,
            )
            response_402 = envelope["challenge"]
        return JSONResponse(status_code=402, content=response_402)

    # ── STEP 5 — Payment present — verify and submit ────────────────
    micro_usdc = int(amount_usdc * 1_000_000)

    provider = FrameworkRegistry.get_settlement_provider("x402-algorand-testnet")
    if provider is None:
        payment_result = await x402_handler.verify_and_submit_payment(
            x_payment_header=x_payment,
            expected_amount_micro=micro_usdc,
            expected_pay_to=pay_to_address,
            session_id=session_id,
        )
    else:
        payment_result = await provider.verify_payment(
            session_id=session_id,
            payment_token=x_payment,
            expected_amount=amount_usdc,
            expected_pay_to=pay_to_address,
        )

    # ── STEP 6 — Record delivery in DB ──────────────────────────────
    is_simulation = payment_result.get("simulation", not payment_result.get("verified", True))
    new_delivery = Delivery(
        session_id=sid,
        tx_id=payment_result["tx_id"],
        amount_usdc=amount_usdc,
        network=payment_result["network"],
        simulation=is_simulation,
        delivered_at=datetime.now(timezone.utc),
    )
    db.add(new_delivery)

    # Update negotiation delivery fields
    neg.delivery_status = "DELIVERED"
    neg.delivery_tx_id = payment_result["tx_id"]
    await db.flush()

    # ── STEP 7 — Audit log ──────────────────────────────────────────
    await audit_logger.append(
        entity_type="negotiation",
        entity_id=session_id,
        action="X402_PAYMENT_VERIFIED",
        actor_id=str(neg.buyer_enterprise_id),
        payload={
            "tx_id": payment_result["tx_id"],
            "amount_usdc": amount_usdc,
            "network": payment_result["network"],
            "simulation": is_simulation,
            "confirmed_round": payment_result.get("confirmed_round"),
        },
        db_session=db,
    )

    await db.commit()

    # ── STEP 8 — Return 200 ─────────────────────────────────────────
    return {
        "delivered": True,
        "session_id": session_id,
        "payment_tx_id": payment_result["tx_id"],
        "network": payment_result["network"],
        "amount_usdc": amount_usdc,
        "x402_verified": True,
        "simulation": is_simulation,
        "confirmed_round": payment_result.get("confirmed_round"),
    }
