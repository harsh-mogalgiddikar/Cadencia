"""
api/routes/treasury.py — Treasury dashboard API endpoints.

GET  /treasury/platform                   — platform-wide summary
GET  /treasury/{enterprise_id}            — enterprise summary
GET  /treasury/{enterprise_id}/exposure   — exposure report
GET  /treasury/{enterprise_id}/timeline   — negotiation timeline
GET  /treasury/{enterprise_id}/strategy   — strategy performance
GET  /treasury/{enterprise_id}/counterparties — counterparty analysis
GET  /treasury/session/{session_id}/pnl   — session P&L
GET  /treasury/session/{session_id}/llm   — LLM performance
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from db.database import get_db
from treasury.analytics import treasury_analytics
from treasury.dashboard import treasury_dashboard

router = APIRouter(prefix="/treasury", tags=["Treasury"])


def _get_redis():
    from api.main import redis_manager
    return redis_manager.client


@router.get("/platform")
async def get_platform_summary(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Platform-wide treasury summary."""
    return await treasury_dashboard.get_platform_summary(db)


@router.get("/session/{session_id}/pnl")
async def get_session_pnl(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """P&L for authenticated enterprise in this session."""
    enterprise_id = str(user.enterprise_id)
    rc = _get_redis()
    return await treasury_dashboard.get_session_pnl(
        session_id, enterprise_id, db, rc
    )


@router.get("/session/{session_id}/llm")
async def get_session_llm_performance(
    session_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM advisory performance for session."""
    return await treasury_analytics.get_llm_performance(session_id, db)


@router.get("/{enterprise_id}")
async def get_enterprise_summary(
    enterprise_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enterprise treasury summary."""
    return await treasury_dashboard.get_enterprise_summary(enterprise_id, db)


@router.get("/{enterprise_id}/exposure")
async def get_exposure_report(
    enterprise_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exposure report for enterprise."""
    return await treasury_dashboard.get_exposure_report(enterprise_id, db)


@router.get("/{enterprise_id}/timeline")
async def get_negotiation_timeline(
    enterprise_id: str,
    days: int = 30,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Negotiation timeline for last N days."""
    return await treasury_analytics.get_negotiation_timeline(
        enterprise_id, days=days, db_session=db
    )


@router.get("/{enterprise_id}/strategy")
async def get_strategy_performance(
    enterprise_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Strategy performance breakdown."""
    return await treasury_analytics.get_strategy_performance(
        enterprise_id, db_session=db
    )


@router.get("/{enterprise_id}/counterparties")
async def get_counterparty_analysis(
    enterprise_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Counterparty analysis."""
    return await treasury_analytics.get_counterparty_analysis(
        enterprise_id, db_session=db
    )
