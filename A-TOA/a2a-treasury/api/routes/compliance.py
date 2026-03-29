"""
api/routes/compliance.py — FEMA compliance API endpoints.

GET  /compliance/session/{session_id}       — session compliance record
POST /compliance/check                      — dry compliance check
GET  /compliance/{enterprise_id}/history    — enterprise compliance history
GET  /compliance/purpose-codes              — RBI purpose code reference
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.database import get_db
from compliance.fema_engine import fema_engine
from compliance.rbi_codes import DEFAULT_TRADE_PURPOSE_CODE, RBI_PURPOSE_CODES
from core.fx_engine import fx_engine

router = APIRouter(prefix="/compliance", tags=["Compliance"])


class ComplianceCheckRequest(BaseModel):
    buyer_enterprise_id: str
    seller_enterprise_id: str
    inr_amount: float
    purpose_code: str = DEFAULT_TRADE_PURPOSE_CODE


@router.get("/purpose-codes")
async def get_purpose_codes():
    """Returns full list of RBI purpose codes."""
    return {"codes": RBI_PURPOSE_CODES}


@router.get("/session/{session_id}")
async def get_session_compliance(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns compliance record for a session."""
    record = await fema_engine.get_compliance_record(session_id, db)
    if not record:
        raise HTTPException(404, "No compliance record for this session")
    return record.model_dump()


@router.post("/check")
async def dry_compliance_check(
    body: ComplianceCheckRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dry compliance check — does NOT write to DB.
    Use for pre-flight checks before session creation.
    """
    from api.main import redis_manager
    rc = redis_manager.client
    # Get FX rate for USD equivalent
    quote = await fx_engine.get_rate(rc, db)
    usdc_amount = body.inr_amount * quote.sell_rate

    result = await fema_engine.check_session_compliance(
        session_id="dry-check",
        buyer_enterprise_id=body.buyer_enterprise_id,
        seller_enterprise_id=body.seller_enterprise_id,
        inr_amount=body.inr_amount,
        usdc_amount=usdc_amount,
        purpose_code=body.purpose_code,
        db_session=db,
    )
    return result.model_dump()


@router.get("/{enterprise_id}/history")
async def get_compliance_history(
    enterprise_id: str,
    limit: int = 50,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns compliance history for enterprise."""
    history = await fema_engine.get_enterprise_compliance_history(
        enterprise_id, db, limit=limit
    )
    return {"records": history, "count": len(history)}
