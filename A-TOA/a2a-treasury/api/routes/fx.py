"""
api/routes/fx.py — FX rate endpoints.

GET  /fx/rate              — current INR/USDC rate
GET  /fx/session/{id}      — session-locked rate
POST /fx/convert           — convert INR ↔ USDC
GET  /fx/history           — recent FX quotes
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.database import get_db
from core.fx_engine import fx_engine

router = APIRouter(prefix="/fx", tags=["FX"])


def _get_redis():
    from api.main import redis_manager
    return redis_manager.client


class ConvertRequest(BaseModel):
    amount: float
    from_currency: str  # "INR" | "USDC"
    to_currency: str  # "USDC" | "INR"
    session_id: str | None = None


@router.get("/rate")
async def get_fx_rate(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns current INR/USDC rate (cached or fresh)."""
    rc = _get_redis()
    quote = await fx_engine.get_rate(rc, db)
    return {
        "quote_id": quote.quote_id,
        "mid_rate": quote.mid_rate,
        "buy_rate": quote.buy_rate,
        "sell_rate": quote.sell_rate,
        "spread_bps": quote.spread_bps,
        "source": quote.source,
        "fetched_at": quote.fetched_at,
        "expires_at": quote.expires_at,
    }


@router.get("/session/{session_id}")
async def get_session_fx_rate(
    session_id: str,
    user=Depends(get_current_user),
):
    """Returns FX rate locked to a specific session."""
    rc = _get_redis()
    try:
        quote = await fx_engine.get_session_rate(session_id, rc)
    except ValueError:
        raise HTTPException(404, "No FX rate locked for this session")
    return {
        "quote_id": quote.quote_id,
        "mid_rate": quote.mid_rate,
        "buy_rate": quote.buy_rate,
        "sell_rate": quote.sell_rate,
        "spread_bps": quote.spread_bps,
        "source": quote.source,
        "session_id": quote.session_id,
        "fetched_at": quote.fetched_at,
    }


@router.post("/convert")
async def convert_currency(
    body: ConvertRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Convert INR ↔ USDC using live or session-locked rate."""
    rc = _get_redis()
    if body.session_id:
        try:
            quote = await fx_engine.get_session_rate(body.session_id, rc)
        except ValueError:
            raise HTTPException(404, "No FX rate locked for this session")
    else:
        quote = await fx_engine.get_rate(rc, db)

    if body.from_currency.upper() == "INR" and body.to_currency.upper() == "USDC":
        conv = fx_engine.convert_inr_to_usdc(body.amount, quote)
    elif body.from_currency.upper() == "USDC" and body.to_currency.upper() == "INR":
        conv = fx_engine.convert_usdc_to_inr(body.amount, quote)
    else:
        raise HTTPException(400, "Supported conversions: INR→USDC, USDC→INR")

    return conv.model_dump()


@router.get("/history")
async def get_fx_history(
    limit: int = 50,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns last N FX quotes."""
    history = await fx_engine.get_fx_history(limit=limit, db_session=db)
    return {"quotes": history, "count": len(history)}
