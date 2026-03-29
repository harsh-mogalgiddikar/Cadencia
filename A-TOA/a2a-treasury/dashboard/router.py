"""
dashboard/router.py — FastAPI router for HTML dashboard pages.

RULE 20: All dashboard routes are GET only — READ-ONLY.
RULE 21: Templates NEVER expose JWT tokens, private keys, or credentials.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db

logger = logging.getLogger("a2a_treasury.dashboard")

router = APIRouter(tags=["Dashboard"])

# Templates directory
_template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard_index(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Platform overview dashboard."""
    from treasury.dashboard import treasury_dashboard
    from core.fx_engine import fx_engine
    from api.main import redis_manager
    from db.models import Negotiation, Enterprise
    from sqlalchemy import select

    platform = await treasury_dashboard.get_platform_summary(db)

    # Recent sessions
    result = await db.execute(
        select(Negotiation).order_by(Negotiation.initiated_at.desc()).limit(10)
    )
    sessions = result.scalars().all()

    recent = []
    for s in sessions:
        # Get enterprise names
        buyer_r = await db.execute(
            select(Enterprise).where(
                Enterprise.enterprise_id == s.buyer_enterprise_id
            )
        )
        seller_r = await db.execute(
            select(Enterprise).where(
                Enterprise.enterprise_id == s.seller_enterprise_id
            )
        )
        buyer = buyer_r.scalar_one_or_none()
        seller = seller_r.scalar_one_or_none()
        recent.append({
            "session_id": str(s.session_id)[:8] + "...",
            "session_id_full": str(s.session_id),
            "buyer": buyer.legal_name if buyer else "Unknown",
            "seller": seller.legal_name if seller else "Unknown",
            "status": s.status,
            "agreed_value": f"₹{float(s.final_agreed_value):,.0f}" if s.final_agreed_value else "—",
            "rounds": s.current_round or 0,
            "created": s.initiated_at.strftime("%Y-%m-%d %H:%M") if s.initiated_at else "—",
        })

    # FX rate
    try:
        rc = redis_manager.client
        fx = await fx_engine.get_rate(rc, db)
        fx_rate = f"{fx.sell_rate:.6f}"
        fx_source = fx.source
    except Exception:
        fx_rate = "N/A"
        fx_source = "unavailable"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "platform": platform,
        "recent_sessions": recent,
        "fx_rate": fx_rate,
        "fx_source": fx_source,
    })


@router.get("/session/{session_id}", response_class=HTMLResponse)
async def dashboard_session(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Single session detail view."""
    from treasury.dashboard import treasury_dashboard
    from compliance.fema_engine import fema_engine
    from db.models import Negotiation, Offer, EscrowContract, Enterprise, AuditLog
    from sqlalchemy import select
    import uuid

    sid = uuid.UUID(session_id)

    # Session
    neg_r = await db.execute(
        select(Negotiation).where(Negotiation.session_id == sid)
    )
    neg = neg_r.scalar_one_or_none()
    if not neg:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    # Enterprise names
    buyer_r = await db.execute(
        select(Enterprise).where(Enterprise.enterprise_id == neg.buyer_enterprise_id)
    )
    seller_r = await db.execute(
        select(Enterprise).where(Enterprise.enterprise_id == neg.seller_enterprise_id)
    )
    buyer = buyer_r.scalar_one_or_none()
    seller = seller_r.scalar_one_or_none()

    # Offers
    offers_r = await db.execute(
        select(Offer).where(Offer.session_id == sid).order_by(Offer.timestamp)
    )
    offers = [
        {
            "round": o.round,
            "role": o.agent_role,
            "value": f"₹{float(o.value):,.0f}" if o.value else "—",
            "action": o.action,
            "confidence": f"{float(o.confidence):.2f}" if o.confidence else "—",
            "strategy": o.strategy_tag or "—",
            "time": o.timestamp.strftime("%H:%M:%S") if o.timestamp else "",
        }
        for o in offers_r.scalars().all()
    ]

    # Compliance
    compliance = await fema_engine.get_compliance_record(session_id, db)
    comp_data = compliance.model_dump() if compliance else None

    # Escrow
    escrow_r = await db.execute(
        select(EscrowContract).where(EscrowContract.session_id == sid)
    )
    escrow = escrow_r.scalars().first()
    escrow_data = None
    if escrow:
        is_live = escrow.contract_ref and len(escrow.contract_ref) == 58
        escrow_data = {
            "contract_ref": escrow.contract_ref or "N/A",
            "status": escrow.status or "N/A",
            "amount": f"₹{float(escrow.amount):,.0f}" if escrow.amount else "—",
            "network": escrow.network_id or "N/A",
            "mode": "LIVE" if is_live else "SIMULATION",
            "explorer": f"https://lora.algokit.io/testnet/account/{escrow.contract_ref}" if is_live else None,
        }

    # Audit entries (limited)
    audit_r = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == sid)
        .order_by(AuditLog.timestamp)
        .limit(20)
    )
    audit = [
        {
            "time": a.timestamp.strftime("%H:%M:%S") if a.timestamp else "",
            "action": a.action,
            "actor": a.actor_id[:12] + "..." if len(a.actor_id) > 12 else a.actor_id,
            "hash": a.this_hash[:12] + "..." if a.this_hash else "",
        }
        for a in audit_r.scalars().all()
    ]

    return templates.TemplateResponse("session.html", {
        "request": request,
        "session_id": session_id,
        "session": {
            "status": neg.status,
            "rounds": neg.current_round or 0,
            "max_rounds": neg.max_rounds,
            "buyer": buyer.legal_name if buyer else "Unknown",
            "seller": seller.legal_name if seller else "Unknown",
            "agreed_value": f"₹{float(neg.final_agreed_value):,.0f}" if neg.final_agreed_value else "—",
            "fx_rate": f"{float(neg.fx_rate_locked):.8f}" if neg.fx_rate_locked else "N/A",
        },
        "offers": offers,
        "compliance": comp_data,
        "escrow": escrow_data,
        "audit_entries": audit,
    })


@router.get("/treasury/{enterprise_id}", response_class=HTMLResponse)
async def dashboard_treasury(
    request: Request,
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Enterprise treasury view."""
    from treasury.dashboard import treasury_dashboard
    from treasury.analytics import treasury_analytics

    summary = await treasury_dashboard.get_enterprise_summary(enterprise_id, db)
    timeline = await treasury_analytics.get_negotiation_timeline(
        enterprise_id, days=30, db_session=db
    )
    counterparties = await treasury_analytics.get_counterparty_analysis(
        enterprise_id, db_session=db
    )
    exposure = await treasury_dashboard.get_exposure_report(enterprise_id, db)

    return templates.TemplateResponse("treasury.html", {
        "request": request,
        "enterprise_id": enterprise_id,
        "summary": summary,
        "timeline": timeline,
        "counterparties": counterparties,
        "exposure": exposure,
    })
