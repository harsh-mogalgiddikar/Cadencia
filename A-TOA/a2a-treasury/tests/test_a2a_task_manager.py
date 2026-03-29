"""
tests/test_a2a_task_manager.py — Phase 2 A2A Task Manager tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from a2a_protocol.task_manager import A2ATaskManager, A2ATaskStatus, A2ATask


@pytest.mark.asyncio
async def test_submit_task_transitions_to_working():
    manager = A2ATaskManager()
    redis = MagicMock()
    redis.client.set = AsyncMock()
    redis.client.sadd = AsyncMock()
    redis.client.expire = AsyncMock()
    task = await manager.submit_task(
        session_id="s1",
        from_agent="buyer",
        to_agent="neutral",
        task_type="offer",
        payload={"session_id": "s1", "agent_role": "buyer", "round": 1},
        redis_client=redis,
    )
    assert task.status == A2ATaskStatus.WORKING
    assert task.from_agent == "buyer"
    assert task.to_agent == "neutral"


@pytest.mark.asyncio
async def test_get_task_returns_none_when_missing():
    manager = A2ATaskManager()
    redis = MagicMock()
    redis.client.get = AsyncMock(return_value=None)
    out = await manager.get_task("task-nonexistent", redis)
    assert out is None
