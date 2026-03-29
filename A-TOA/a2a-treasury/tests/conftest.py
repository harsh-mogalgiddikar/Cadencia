"""
tests/conftest.py — pytest fixtures for A2A Treasury Network.

Provides: async DB session, fakeredis client, FastAPI test client,
and factory fixtures for creating test data.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Must set env vars BEFORE importing app modules
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_testing_only_64chars_0000000000000000000000")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ENVIRONMENT", "testing")

from db.models import Base, Enterprise, User, AgentConfig, TreasuryPolicy, Wallet


# ─── Event loop ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── PostgreSQL test database (Docker container on localhost) ───────────────
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://a2a:password@localhost:5432/a2a_treasury",
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Async test database session using Docker PostgreSQL."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with factory() as session:
        yield session
        # Roll back any uncommitted changes from the test
        await session.rollback()

    # Drop all tables after each test to ensure isolation
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ─── Fake Redis ─────────────────────────────────────────────────────────────
class FakeRedis:
    """Minimal in-memory Redis mock for testing."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}
        self._sorted_sets: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._ttls.pop(key, None)

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0"))
        current += 1
        self._store[key] = str(current)
        return current

    async def ttl(self, key: str) -> int:
        return self._ttls.get(key, -1)

    async def expire(self, key: str, seconds: int) -> None:
        self._ttls[key] = seconds

    async def zadd(self, key: str, mapping: dict) -> None:
        if key not in self._sorted_sets:
            self._sorted_sets[key] = {}
        self._sorted_sets[key].update(mapping)

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> None:
        if key in self._sorted_sets:
            self._sorted_sets[key] = {
                k: v for k, v in self._sorted_sets[key].items()
                if not (min_score <= v <= max_score)
            }

    async def zcard(self, key: str) -> int:
        return len(self._sorted_sets.get(key, {}))

    def pipeline(self, transaction: bool = False):
        return FakePipeline(self)


class FakePipeline:
    """Fake Redis pipeline for testing."""

    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._commands: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def set(self, key: str, value: str) -> "FakePipeline":
        self._commands.append(("set", key, value))
        return self

    def expire(self, key: str, seconds: int) -> "FakePipeline":
        self._commands.append(("expire", key, seconds))
        return self

    def zremrangebyscore(self, key: str, min_s: float, max_s: float) -> "FakePipeline":
        self._commands.append(("zremrangebyscore", key, min_s, max_s))
        return self

    def zadd(self, key: str, mapping: dict) -> "FakePipeline":
        self._commands.append(("zadd", key, mapping))
        return self

    def zcard(self, key: str) -> "FakePipeline":
        self._commands.append(("zcard", key))
        return self

    async def execute(self) -> list:
        results = []
        for cmd in self._commands:
            if cmd[0] == "set":
                await self._redis.set(cmd[1], cmd[2])
                results.append(True)
            elif cmd[0] == "expire":
                await self._redis.expire(cmd[1], cmd[2])
                results.append(True)
            elif cmd[0] == "zremrangebyscore":
                await self._redis.zremrangebyscore(cmd[1], cmd[2], cmd[3])
                results.append(0)
            elif cmd[0] == "zadd":
                await self._redis.zadd(cmd[1], cmd[2])
                results.append(1)
            elif cmd[0] == "zcard":
                count = await self._redis.zcard(cmd[1])
                results.append(count)
        return results


class FakeRedisSessionManager:
    """Redis session manager backed by FakeRedis for testing."""

    def __init__(self):
        self._client = FakeRedis()

    @property
    def client(self):
        return self._client

    async def connect(self):
        pass

    async def close(self):
        pass

    async def set_session_state(self, session_id, state, ttl_seconds):
        import json
        await self._client.set(f"session:{session_id}", json.dumps(state, default=str), ex=ttl_seconds)

    async def get_session_state(self, session_id):
        import json
        raw = await self._client.get(f"session:{session_id}")
        return json.loads(raw) if raw else None

    async def update_session_field(self, session_id, field, value):
        import json
        raw = await self._client.get(f"session:{session_id}")
        if raw:
            state = json.loads(raw)
            state[field] = value
            ttl = await self._client.ttl(f"session:{session_id}")
            await self._client.set(f"session:{session_id}", json.dumps(state, default=str), ex=ttl if ttl > 0 else 3600)

    async def delete_session(self, session_id):
        await self._client.delete(f"session:{session_id}")

    async def set_valuation_snapshot(self, session_id, snapshot):
        import json
        existing = await self._client.get(f"valuation:{session_id}")
        if existing is None:
            await self._client.set(f"valuation:{session_id}", json.dumps(snapshot, default=str), ex=3600)

    async def get_valuation_snapshot(self, session_id):
        import json
        raw = await self._client.get(f"valuation:{session_id}")
        return json.loads(raw) if raw else None

    async def increment_failure_count(self, session_id, agent_role):
        return await self._client.incr(f"failures:{session_id}:{agent_role}")

    async def get_failure_count(self, session_id, agent_role):
        raw = await self._client.get(f"failures:{session_id}:{agent_role}")
        return int(raw) if raw else 0

    async def reset_failure_count(self, session_id, agent_role):
        await self._client.delete(f"failures:{session_id}:{agent_role}")

    async def check_rate_limit(self, session_id, agent_role):
        return True  # No rate limiting in tests

    async def update_stall_counter(self, session_id, delta, prev_offer):
        stall_threshold = 0.002 * prev_offer if prev_offer > 0 else 0.0
        if abs(delta) < stall_threshold:
            count = await self._client.incr(f"stall:{session_id}")
        else:
            await self._client.set(f"stall:{session_id}", "0")
            count = 0
        return int(count)

    async def rebuild_from_postgres(self, session_id, db_session):
        return None

    async def store_refresh_token_hash(self, user_id, token_hash):
        await self._client.set(f"refresh:{user_id}", token_hash, ex=7*24*3600)

    async def get_refresh_token_hash(self, user_id):
        return await self._client.get(f"refresh:{user_id}")

    async def invalidate_refresh_token(self, user_id):
        await self._client.delete(f"refresh:{user_id}")


@pytest.fixture
def fake_redis():
    return FakeRedisSessionManager()


# ─── Factory fixtures ──────────────────────────────────────────────────────
import bcrypt

BCRYPT_COST = 4  # Use low cost for fast tests


async def create_enterprise(
    db: AsyncSession,
    legal_name: str = "Test Corp",
    kyc_status: str = "ACTIVE",
    wallet_address: str | None = None,
) -> Enterprise:
    ent = Enterprise(
        enterprise_id=uuid.uuid4(),
        legal_name=legal_name,
        kyc_status=kyc_status,
        wallet_address=wallet_address or f"ALGO_{uuid.uuid4().hex[:16]}",
    )
    db.add(ent)
    await db.flush()
    return ent


async def create_user(
    db: AsyncSession,
    enterprise_id: uuid.UUID,
    email: str | None = None,
    role: str = "admin",
    password: str = "testpassword123",
) -> User:
    pw_hash = bcrypt.hashpw(
        password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST),
    ).decode()
    user = User(
        user_id=uuid.uuid4(),
        enterprise_id=enterprise_id,
        email=email or f"test_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        password_hash=pw_hash,
    )
    db.add(user)
    await db.flush()
    return user


async def create_agent_config(
    db: AsyncSession,
    enterprise_id: uuid.UUID,
    agent_role: str = "buyer",
    intrinsic_value: float = 92000.0,
    risk_factor: float = 0.12,
    negotiation_margin: float = 0.08,
    concession_curve: dict | None = None,
    budget_ceiling: float | None = 96000.0,
    max_exposure: float = 100000.0,
    max_rounds: int = 8,
    timeout_seconds: int = 3600,
) -> AgentConfig:
    if concession_curve is None:
        concession_curve = {"1": 0.06, "2": 0.04, "3": 0.025, "4": 0.015, "5": 0.008}

    config = AgentConfig(
        config_id=uuid.uuid4(),
        enterprise_id=enterprise_id,
        agent_role=agent_role,
        intrinsic_value=Decimal(str(intrinsic_value)),
        risk_factor=Decimal(str(risk_factor)),
        negotiation_margin=Decimal(str(negotiation_margin)),
        concession_curve=concession_curve,
        budget_ceiling=Decimal(str(budget_ceiling)) if budget_ceiling else None,
        max_exposure=Decimal(str(max_exposure)),
        max_rounds=max_rounds,
        timeout_seconds=timeout_seconds,
    )
    db.add(config)
    await db.flush()
    return config


async def create_treasury_policy(
    db: AsyncSession,
    enterprise_id: uuid.UUID,
) -> TreasuryPolicy:
    policy = TreasuryPolicy(
        policy_id=uuid.uuid4(),
        enterprise_id=enterprise_id,
        risk_tolerance="balanced",
        active=True,
    )
    db.add(policy)
    await db.flush()
    return policy
