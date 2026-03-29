"""
compliance/fema_records.py — FEMA record storage and retrieval.

Phase 3: Fully implemented — wraps FEMAComplianceEngine for backward compatibility.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from compliance.fema_engine import fema_engine, FEMACheckResult


async def create_fema_record(
    session_id: str,
    enterprise_id: str,
    purpose_code: str = "P0103",
    counterparty_country: str = "IN",
    invoice_ref: str | None = None,
    inr_amount: float = 0.0,
    usdc_amount: float = 0.0,
    db_session: AsyncSession | None = None,
) -> dict:
    """
    Create a FEMA compliance record for a session.
    Delegates to FEMAComplianceEngine.
    """
    if not db_session:
        return {"status": "SKIPPED", "reason": "No DB session"}

    # Run compliance check
    result = await fema_engine.check_session_compliance(
        session_id=session_id,
        buyer_enterprise_id=enterprise_id,
        seller_enterprise_id=enterprise_id,
        inr_amount=inr_amount,
        usdc_amount=usdc_amount,
        purpose_code=purpose_code,
        db_session=db_session,
    )

    # Record result
    record_id = await fema_engine.record_compliance(
        session_id=session_id,
        enterprise_id=enterprise_id,
        check_result=result,
        db_session=db_session,
    )

    return {
        "record_id": record_id,
        "status": result.status.value,
        "purpose_code": result.purpose_code,
        "transaction_type": result.transaction_type,
    }


async def get_fema_status(session_id: str, db_session: AsyncSession | None = None) -> dict:
    """Get FEMA compliance status for a session."""
    if not db_session:
        return {"status": "UNKNOWN", "reason": "No DB session"}

    record = await fema_engine.get_compliance_record(session_id, db_session)
    if not record:
        return {"status": "NOT_CHECKED"}

    return record.model_dump()
