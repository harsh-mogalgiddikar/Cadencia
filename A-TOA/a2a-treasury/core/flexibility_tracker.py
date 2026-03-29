"""
core/flexibility_tracker.py — Opponent Behavioral Metrics.

Tracks opponent concession patterns and cooperation signals per session.
Stored in Redis: flexibility:{session_id}:{observing_role}.
"""
from __future__ import annotations

import json
from typing import Any


DEFAULT_FLEXIBILITY = 0.5
FLEXIBILITY_KEY_PREFIX = "flexibility"
TTL_SECONDS = 3600


class FlexibilityTracker:
    """Tracks opponent behavioral metrics across rounds."""

    def _key(self, session_id: str, observing_role: str) -> str:
        return f"{FLEXIBILITY_KEY_PREFIX}:{session_id}:{observing_role}"

    async def update(
        self,
        session_id: str,
        observing_role: str,
        opponent_offer: float | None,
        prev_opponent_offer: float | None,
        round_num: int,
        response_time_seconds: float,
        redis_client: Any,
    ) -> None:
        """Update flexibility metrics after observing an opponent move."""
        if opponent_offer is None:
            return

        key = self._key(session_id, observing_role)
        raw = await redis_client.client.get(key)
        if raw:
            data = json.loads(raw)
            old_flexibility = float(data.get("flexibility_score", DEFAULT_FLEXIBILITY))
            offer_history = list(data.get("offer_history", []))
            total_rounds = int(data.get("total_rounds_observed", 0))
            response_times = list(data.get("response_time_history", []))
        else:
            old_flexibility = DEFAULT_FLEXIBILITY
            offer_history = []
            total_rounds = 0
            response_times = []

        # Concession from this move
        if prev_opponent_offer is not None and prev_opponent_offer > 0:
            concession = abs(opponent_offer - prev_opponent_offer)
            concession_pct = concession / prev_opponent_offer
            new_flexibility = min(1.0, concession_pct / 0.05)
        else:
            new_flexibility = DEFAULT_FLEXIBILITY

        rolling_flexibility = old_flexibility * 0.7 + new_flexibility * 0.3

        offer_history.append(opponent_offer)
        total_rounds += 1
        response_times.append(response_time_seconds)
        response_time_avg = sum(response_times) / len(response_times) if response_times else 0.0

        # Concession rate (avg concession per round)
        concession_rate = 0.0
        if len(offer_history) >= 2:
            deltas = [
                abs(offer_history[i] - offer_history[i - 1])
                for i in range(1, len(offer_history))
            ]
            concession_rate = sum(deltas) / len(deltas) if deltas else 0.0

        # Pattern detection
        if rolling_flexibility > 0.7:
            pattern = "cooperative"
        elif rolling_flexibility < 0.2:
            pattern = "aggressive"
        elif response_time_avg < 2.0:
            pattern = "strategic"
        else:
            pattern = "stalling"

        payload = {
            "flexibility_score": round(rolling_flexibility, 4),
            "concession_rate": round(concession_rate, 6),
            "response_time_avg": round(response_time_avg, 2),
            "total_rounds_observed": total_rounds,
            "last_offer": opponent_offer,
            "offer_history": offer_history[-50:],  # cap size
            "response_time_history": response_times[-20:],
            "pattern": pattern,
        }
        await redis_client.client.set(
            key,
            json.dumps(payload, default=str),
            ex=TTL_SECONDS,
        )

    async def get(
        self,
        session_id: str,
        observing_role: str,
        redis_client: Any,
    ) -> dict:
        """Returns current flexibility metrics. Defaults if not yet computed."""
        key = self._key(session_id, observing_role)
        raw = await redis_client.client.get(key)
        if raw is None:
            return {
                "flexibility_score": DEFAULT_FLEXIBILITY,
                "concession_rate": 0.0,
                "response_time_avg": 0.0,
                "total_rounds_observed": 0,
                "last_offer": None,
                "offer_history": [],
                "pattern": "strategic",
            }
        return json.loads(raw)

    async def get_flexibility_score(
        self,
        session_id: str,
        observing_role: str,
        redis_client: Any,
    ) -> float:
        """Returns just the float flexibility_score. Default: 0.5"""
        data = await self.get(session_id, observing_role, redis_client)
        return float(data.get("flexibility_score", DEFAULT_FLEXIBILITY))
