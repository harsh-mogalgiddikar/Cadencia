"""Phase 4: FEMA compliance engine tests."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from compliance.fema_engine import FEMAComplianceEngine, FEMAComplianceStatus


@pytest.mark.asyncio
async def test_domestic_transaction_returns_exempt(db_session):
    """MVP: both parties Indian => DOMESTIC => EXEMPT."""
    engine = FEMAComplianceEngine()
    # Use valid UUIDs; engine treats as domestic when both Indian (default)
    result = await engine.check_session_compliance(
        session_id="test-session",
        buyer_enterprise_id="00000000-0000-0000-0000-000000000001",
        seller_enterprise_id="00000000-0000-0000-0000-000000000002",
        inr_amount=100000,
        usdc_amount=1200,
        db_session=db_session,
    )
    assert result.status == FEMAComplianceStatus.EXEMPT
    assert result.transaction_type == "DOMESTIC"


def test_default_purpose_code_is_p0103():
    from compliance.rbi_codes import DEFAULT_TRADE_PURPOSE_CODE
    assert DEFAULT_TRADE_PURPOSE_CODE == "P0103"
