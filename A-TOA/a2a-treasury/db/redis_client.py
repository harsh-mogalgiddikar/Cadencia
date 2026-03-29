"""
db/redis_client.py — Redis session state manager.

Implements: session caching, valuation snapshots, failure tracking,
rate limiting (sliding window), stall detection, refresh token storage,
and PostgreSQL fallback rebuild.
"""
from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from db.database import get_session_factory


class RedisSessionManager:
    """Async Redis wrapper for all session-related state ops."""

    def __init__(self, redis_url: str = "redis://redis:6379/0") -> None:
        self._url = redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = aioredis.from_url(
                self._url, decode_responses=True,
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    # ─── session state ──────────────────────────────────────────────────────
    async def set_session_state(
        self, session_id: str, state: dict, ttl_seconds: int,
    ) -> None:
        """Serialize state dict to JSON + store with TTL."""
        await self.client.set(
            f"session:{session_id}", json.dumps(state, default=str), ex=ttl_seconds,
        )

    async def get_session_state(self, session_id: str) -> dict | None:
        raw = await self.client.get(f"session:{session_id}")
        if raw is None:
            return None
        return json.loads(raw)

    async def update_session_field(
        self, session_id: str, field: str, value: Any,
    ) -> None:
        """Atomically update one field in session state JSON via pipeline."""
        key = f"session:{session_id}"
        async with self.client.pipeline(transaction=True) as pipe:
            raw = await self.client.get(key)
            if raw is None:
                return
            state = json.loads(raw)
            ttl = await self.client.ttl(key)
            state[field] = value
            pipe.set(key, json.dumps(state, default=str))
            if ttl > 0:
                pipe.expire(key, ttl)
            await pipe.execute()

    async def delete_session(self, session_id: str) -> None:
        await self.client.delete(f"session:{session_id}")

    # ─── valuation snapshot ─────────────────────────────────────────────────
    async def set_valuation_snapshot(
        self, session_id: str, snapshot: dict,
    ) -> None:
        """Immutable once set — NEVER overwrite."""
        key = f"valuation:{session_id}"
        existing = await self.client.get(key)
        if existing is not None:
            return  # already set, immutable
        # use the session TTL for consistency
        session_ttl = await self.client.ttl(f"session:{session_id}")
        ttl = session_ttl if session_ttl > 0 else 3600
        await self.client.set(key, json.dumps(snapshot, default=str), ex=ttl)

    async def get_valuation_snapshot(self, session_id: str) -> dict | None:
        raw = await self.client.get(f"valuation:{session_id}")
        return json.loads(raw) if raw else None

    # ─── failure tracking ───────────────────────────────────────────────────
    async def increment_failure_count(
        self, session_id: str, agent_role: str,
    ) -> int:
        key = f"failures:{session_id}:{agent_role}"
        count = await self.client.incr(key)
        session_ttl = await self.client.ttl(f"session:{session_id}")
        if session_ttl > 0:
            await self.client.expire(key, session_ttl)
        return int(count)

    async def get_failure_count(
        self, session_id: str, agent_role: str,
    ) -> int:
        raw = await self.client.get(f"failures:{session_id}:{agent_role}")
        return int(raw) if raw else 0

    async def reset_failure_count(
        self, session_id: str, agent_role: str,
    ) -> None:
        await self.client.delete(f"failures:{session_id}:{agent_role}")

    # ─── Phase 4: Enterprise rate limits ─────────────────────────────────────
    MAX_SESSIONS_PER_ENTERPRISE_PER_HOUR = 10
    MAX_API_CALLS_PER_ENTERPRISE_PER_MINUTE = 100
    MAX_WEBHOOK_TESTS_PER_ENTERPRISE_PER_HOUR = 5

    async def check_session_rate_limit(self, enterprise_id: str) -> bool:
        """True if under limit (max 10 sessions per enterprise per hour)."""
        key = f"rate:sessions:{enterprise_id}:{int(time.time() // 3600)}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, 3600)
        return count <= self.MAX_SESSIONS_PER_ENTERPRISE_PER_HOUR

    async def check_api_rate_limit(self, enterprise_id: str) -> bool:
        """True if under limit (max 100 API calls per enterprise per minute)."""
        key = f"rate:api:{enterprise_id}:{int(time.time() // 60)}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, 60)
        return count <= self.MAX_API_CALLS_PER_ENTERPRISE_PER_MINUTE

    # ─── rate limiting (sliding window) ─────────────────────────────────────
    async def check_rate_limit(
        self, session_id: str, agent_role: str,
    ) -> bool:
        """True if allowed, False if rate-limited. Max 1 action per 2s."""
        key = f"ratelimit:{session_id}:{agent_role}"
        now = time.time()
        window = 2.0  # seconds
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, int(window) + 1)
            results = await pipe.execute()
        count = results[2]
        return count <= 1

    # ─── stall detection ────────────────────────────────────────────────────
    async def update_stall_counter(
        self, session_id: str, delta: float, prev_offer: float,
    ) -> int:
        key = f"stall:{session_id}"
        stall_threshold = 0.002 * prev_offer if prev_offer > 0 else 0.0
        if abs(delta) < stall_threshold:
            count = await self.client.incr(key)
        else:
            await self.client.set(key, "0")
            count = 0
        session_ttl = await self.client.ttl(f"session:{session_id}")
        if session_ttl > 0:
            await self.client.expire(key, session_ttl)
        return int(count)

    # ─── rebuild from PostgreSQL ────────────────────────────────────────────
    async def rebuild_from_postgres(
        self, session_id: str, db_session: Any,
    ) -> dict | None:
        """
        If Redis key is missing, reconstruct session state from PostgreSQL.
        Must complete within 5 seconds.
        """
        import uuid
        from sqlalchemy import select
        from db.models import Negotiation

        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        result = await db_session.execute(
            select(Negotiation).where(
                Negotiation.session_id == sid,
            ),
        )
        neg = result.scalar_one_or_none()
        if neg is None:
            return None

        expected_turn = "seller" if neg.status == "BUYER_ANCHOR" else "buyer"
        state = {
            "session_id": str(neg.session_id),
            "buyer_enterprise_id": str(neg.buyer_enterprise_id),
            "seller_enterprise_id": str(neg.seller_enterprise_id),
            "status": neg.status,
            "max_rounds": neg.max_rounds,
            "current_round": neg.current_round,
            "timeout_at": neg.timeout_at.isoformat(),
            "outcome": neg.outcome,
            "last_buyer_offer": float(neg.last_buyer_offer) if neg.last_buyer_offer else None,
            "last_seller_offer": float(neg.last_seller_offer) if neg.last_seller_offer else None,
            "stall_counter": neg.stall_counter,
            "buyer_consecutive_failures": neg.buyer_consecutive_failures,
            "seller_consecutive_failures": neg.seller_consecutive_failures,
            "expected_turn": expected_turn,
            "last_actor": "seller" if expected_turn == "buyer" else "buyer",
        }
        # Compute remaining TTL from timeout_at
        import datetime
        remaining = (neg.timeout_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        ttl = max(int(remaining), 60)
        await self.set_session_state(session_id, state, ttl)
        return state

    # ─── refresh token storage ──────────────────────────────────────────────
    async def store_refresh_token_hash(
        self, user_id: str, token_hash: str,
    ) -> None:
        await self.client.set(
            f"refresh:{user_id}", token_hash, ex=7 * 24 * 3600,  # 7 days
        )

    async def get_refresh_token_hash(self, user_id: str) -> str | None:
        return await self.client.get(f"refresh:{user_id}")

    async def invalidate_refresh_token(self, user_id: str) -> None:
        await self.client.delete(f"refresh:{user_id}")
