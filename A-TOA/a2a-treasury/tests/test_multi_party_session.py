"""Phase 4: Multi-party session tests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_validation_rejects_single_seller(db_session):
    from agents.multi_party_session import MultiPartyCoordinator
    from db.redis_client import RedisSessionManager
    coordinator = MultiPartyCoordinator()
    redis = RedisSessionManager(redis_url="redis://localhost:6379/0")
    try:
        await redis.connect()
    except Exception:
        pytest.skip("Redis not available")
    with pytest.raises(ValueError, match="at least 2 sellers"):
        await coordinator.create_multi_session(
            buyer_enterprise_id="00000000-0000-0000-0000-000000000001",
            seller_enterprise_ids=["00000000-0000-0000-0000-000000000002"],
            initial_offer_value=85000,
            timeout_seconds=120,
            db_session=db_session,
            redis_client=redis,
        )


@pytest.mark.asyncio
async def test_validation_rejects_more_than_five_sellers(db_session):
    from agents.multi_party_session import MultiPartyCoordinator
    from db.redis_client import RedisSessionManager
    coordinator = MultiPartyCoordinator()
    redis = RedisSessionManager(redis_url="redis://localhost:6379/0")
    try:
        await redis.connect()
    except Exception:
        pytest.skip("Redis not available")
    with pytest.raises(ValueError, match="at most 5 sellers"):
        await coordinator.create_multi_session(
            buyer_enterprise_id="00000000-0000-0000-0000-000000000001",
            seller_enterprise_ids=[f"00000000-0000-0000-0000-00000000000{i}" for i in range(6)],
            initial_offer_value=85000,
            timeout_seconds=120,
            db_session=db_session,
            redis_client=redis,
        )
