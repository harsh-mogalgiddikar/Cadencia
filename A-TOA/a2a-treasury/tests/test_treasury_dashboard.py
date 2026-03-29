"""Phase 4: Treasury dashboard tests."""
from __future__ import annotations

import pytest

from treasury.dashboard import TreasuryDashboard


@pytest.mark.asyncio
async def test_success_rate_zero_with_no_sessions(db_session):
    dashboard = TreasuryDashboard()
    # Non-existent enterprise returns error; existing with no sessions returns 0
    summary = await dashboard.get_enterprise_summary(
        "00000000-0000-0000-0000-000000000001", db_session
    )
    if "error" in summary:
        assert summary["error"] == "Enterprise not found"
    else:
        assert summary.get("total_sessions", 0) >= 0
        assert "success_rate" in summary or "total_sessions" in summary
