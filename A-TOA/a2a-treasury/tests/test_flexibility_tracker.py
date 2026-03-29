"""
tests/test_flexibility_tracker.py — Phase 2 Flexibility Tracker tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.flexibility_tracker import FlexibilityTracker, DEFAULT_FLEXIBILITY


@pytest.mark.asyncio
async def test_get_returns_default_when_empty():
    tracker = FlexibilityTracker()
    redis = MagicMock()
    redis.client.get = AsyncMock(return_value=None)
    data = await tracker.get("session-1", "buyer", redis)
    assert data["flexibility_score"] == DEFAULT_FLEXIBILITY
    assert data["total_rounds_observed"] == 0


@pytest.mark.asyncio
async def test_update_then_get():
    tracker = FlexibilityTracker()
    redis = MagicMock()
    redis.client.get = AsyncMock(return_value=None)
    redis.client.set = AsyncMock()
    await tracker.update(
        session_id="s1",
        observing_role="buyer",
        opponent_offer=90.0,
        prev_opponent_offer=92.0,
        round_num=2,
        response_time_seconds=1.5,
        redis_client=redis,
    )
    call_arg = redis.client.set.call_args[0][1]
    import json
    data = json.loads(call_arg)
    assert "flexibility_score" in data
    assert data["total_rounds_observed"] == 1
    assert data["last_offer"] == 90.0


@pytest.mark.asyncio
async def test_get_flexibility_score_default():
    tracker = FlexibilityTracker()
    redis = MagicMock()
    redis.client.get = AsyncMock(return_value=None)
    score = await tracker.get_flexibility_score("s1", "seller", redis)
    assert score == DEFAULT_FLEXIBILITY
