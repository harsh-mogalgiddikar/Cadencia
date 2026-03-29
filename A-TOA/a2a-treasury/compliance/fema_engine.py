"""
compliance/fema_engine.py — FEMA compliance engine for cross-border payments.

India's Foreign Exchange Management Act requires all cross-border payments
to be classified by RBI purpose code and reported. This engine enforces those rules.

RULE 18: Compliance is checked for EVERY session. Result always recorded.
         EXEMPT is valid (domestic). Default mode never blocks sessions.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compliance.rbi_codes import DEFAULT_TRADE_PURPOSE_CODE, RBI_PURPOSE_CODES
from db.models import ComplianceRecord, Enterprise

logger = logging.getLogger("a2a_treasury.compliance")

# ─── Settings ───────────────────────────────────────────────────────────────────
FEMA_ODI_LIMIT_USD = float(os.getenv("FEMA_ODI_LIMIT_USD", "250000"))
FEMA_FDI_LIMIT_USD = float(os.getenv("FEMA_FDI_LIMIT_USD", "500000"))
COMPLIANCE_STRICT_MODE = os.getenv("COMPLIANCE_STRICT_MODE", "false").lower() == "true"


# ─── Data Models ────────────────────────────────────────────────────────────────
class FEMAComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    WARNING = "WARNING"
    NON_COMPLIANT = "NON_COMPLIANT"
    EXEMPT = "EXEMPT"


class FEMACheckResult(BaseModel):
    status: FEMAComplianceStatus
    purpose_code: str
    purpose_label: str
    transaction_type: str  # "ODI" | "FDI" | "DOMESTIC"
    inr_amount: float
    usdc_amount: float
    usd_equivalent: float
    limit_applicable: float
    limit_utilization_pct: float
    warnings: list[str]
    blocking_reasons: list[str]
    checked_at: str


# ─── Engine ─────────────────────────────────────────────────────────────────────
class FEMAComplianceEngine:
    """FEMA compliance check and recording engine."""

    async def check_session_compliance(
        self,
        session_id: str,
        buyer_enterprise_id: str,
        seller_enterprise_id: str,
        inr_amount: float,
        usdc_amount: float,
        purpose_code: str = DEFAULT_TRADE_PURPOSE_CODE,
        db_session: AsyncSession | None = None,
    ) -> FEMACheckResult:
        """
        Pre-session compliance check.
        Called before session creation (strict) or after AGREED (always).
        """
        now = datetime.now(timezone.utc).isoformat()
        purpose_label = RBI_PURPOSE_CODES.get(purpose_code, "Unknown purpose code")
        usd_equivalent = usdc_amount  # 1 USDC ≈ 1 USD

        warnings: list[str] = []
        blocking_reasons: list[str] = []

        # Determine if domestic or cross-border
        # For MVP: all enterprises on platform are Indian domestic
        # Cross-border detection would check enterprise.country field
        is_domestic = True
        if db_session:
            try:
                buyer_r = await db_session.execute(
                    select(Enterprise).where(
                        Enterprise.enterprise_id == uuid.UUID(buyer_enterprise_id)
                    )
                )
                seller_r = await db_session.execute(
                    select(Enterprise).where(
                        Enterprise.enterprise_id == uuid.UUID(seller_enterprise_id)
                    )
                )
                buyer = buyer_r.scalar_one_or_none()
                seller = seller_r.scalar_one_or_none()
                # MVP: if PAN starts with pattern, both are Indian
                if buyer and seller:
                    # Both Indian = domestic
                    is_domestic = True
            except Exception:
                pass

        if is_domestic:
            transaction_type = "DOMESTIC"
            limit_applicable = 0.0
            limit_utilization_pct = 0.0
            status = FEMAComplianceStatus.EXEMPT

            # Even domestic gets informational warnings for large amounts
            if usd_equivalent > 10000:
                warnings.append(
                    "Transaction above $10k — SWIFT/RBI reporting may be "
                    "required if converted to cross-border"
                )
        else:
            # Cross-border: determine ODI vs FDI
            transaction_type = "ODI"  # Indian entity paying abroad
            limit_applicable = FEMA_ODI_LIMIT_USD

            if purpose_code.startswith("P13"):
                warnings.append(
                    "Capital account transaction — additional RBI approval "
                    "may be required"
                )
                if purpose_code == "P1302":
                    transaction_type = "FDI"
                    limit_applicable = FEMA_FDI_LIMIT_USD

            limit_utilization_pct = (
                (usd_equivalent / limit_applicable * 100) if limit_applicable else 0.0
            )

            if usd_equivalent > limit_applicable:
                msg = f"Exceeds {transaction_type} per-transaction limit (${limit_applicable:,.0f})"
                if COMPLIANCE_STRICT_MODE:
                    blocking_reasons.append(msg)
                    status = FEMAComplianceStatus.NON_COMPLIANT
                else:
                    warnings.append(msg)
                    status = FEMAComplianceStatus.WARNING
            elif usd_equivalent > 10000:
                warnings.append(
                    "Transaction above $10k — SWIFT/RBI reporting required"
                )
                status = FEMAComplianceStatus.COMPLIANT
            else:
                status = FEMAComplianceStatus.COMPLIANT

        logger.info(
            "Compliance check: session=%s type=%s status=%s amount=$%.2f",
            session_id[:8] if session_id else "N/A",
            transaction_type, status.value, usd_equivalent,
        )

        return FEMACheckResult(
            status=status,
            purpose_code=purpose_code,
            purpose_label=purpose_label,
            transaction_type=transaction_type,
            inr_amount=inr_amount,
            usdc_amount=usdc_amount,
            usd_equivalent=round(usd_equivalent, 2),
            limit_applicable=limit_applicable,
            limit_utilization_pct=round(limit_utilization_pct, 2),
            warnings=warnings,
            blocking_reasons=blocking_reasons,
            checked_at=now,
        )

    async def record_compliance(
        self,
        session_id: str,
        enterprise_id: str,
        check_result: FEMACheckResult,
        db_session: AsyncSession,
    ) -> str:
        """Write compliance record to DB. Returns record_id."""
        record = ComplianceRecord(
            record_id=uuid.uuid4(),
            session_id=uuid.UUID(session_id),
            enterprise_id=uuid.UUID(enterprise_id),
            purpose_code=check_result.purpose_code,
            purpose_label=check_result.purpose_label,
            transaction_type=check_result.transaction_type,
            inr_amount=check_result.inr_amount,
            usdc_amount=check_result.usdc_amount,
            usd_equivalent=check_result.usd_equivalent,
            limit_applicable=check_result.limit_applicable,
            limit_utilization_pct=check_result.limit_utilization_pct,
            status=check_result.status.value,
            warnings=check_result.warnings,
            blocking_reasons=check_result.blocking_reasons,
        )
        db_session.add(record)
        await db_session.flush()

        logger.info(
            "Compliance recorded: session=%s record=%s status=%s",
            session_id[:8], str(record.record_id)[:8], check_result.status.value,
        )
        return str(record.record_id)

    async def get_compliance_record(
        self, session_id: str, db_session: AsyncSession
    ) -> FEMACheckResult | None:
        """Retrieve existing compliance record for a session."""
        result = await db_session.execute(
            select(ComplianceRecord).where(
                ComplianceRecord.session_id == uuid.UUID(session_id)
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None

        return FEMACheckResult(
            status=FEMAComplianceStatus(row.status),
            purpose_code=row.purpose_code,
            purpose_label=row.purpose_label or "",
            transaction_type=row.transaction_type or "DOMESTIC",
            inr_amount=float(row.inr_amount or 0),
            usdc_amount=float(row.usdc_amount or 0),
            usd_equivalent=float(row.usd_equivalent or 0),
            limit_applicable=float(row.limit_applicable or 0),
            limit_utilization_pct=float(row.limit_utilization_pct or 0),
            warnings=row.warnings or [],
            blocking_reasons=row.blocking_reasons or [],
            checked_at=row.checked_at.isoformat() if row.checked_at else "",
        )

    async def get_enterprise_compliance_history(
        self,
        enterprise_id: str,
        db_session: AsyncSession,
        limit: int = 50,
    ) -> list[dict]:
        """Returns compliance history for an enterprise."""
        result = await db_session.execute(
            select(ComplianceRecord)
            .where(ComplianceRecord.enterprise_id == uuid.UUID(enterprise_id))
            .order_by(ComplianceRecord.checked_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "record_id": str(r.record_id),
                "session_id": str(r.session_id) if r.session_id else None,
                "status": r.status,
                "purpose_code": r.purpose_code,
                "transaction_type": r.transaction_type,
                "usd_equivalent": float(r.usd_equivalent or 0),
                "checked_at": r.checked_at.isoformat() if r.checked_at else None,
            }
            for r in rows
        ]


# Module-level singleton
fema_engine = FEMAComplianceEngine()
