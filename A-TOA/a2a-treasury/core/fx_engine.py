"""
core/fx_engine.py — FX rate engine for INR ↔ USDC conversion.

RULE 17: FX rates are LOCKED at session creation and NEVER change mid-session.
The locked rate is the ONLY rate escrow uses for settlement calculations.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import aiohttp
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import FxQuote as FxQuoteModel

logger = logging.getLogger("a2a_treasury.fx")

# ─── Settings ───────────────────────────────────────────────────────────────────
FX_PROVIDER = os.getenv("FX_PROVIDER", "frankfurter")
FX_FALLBACK_RATE = float(os.getenv("FX_FALLBACK_RATE", "0.01193"))
FX_CACHE_TTL_SECONDS = int(os.getenv("FX_CACHE_TTL_SECONDS", "300"))
FX_SPREAD_BPS = int(os.getenv("FX_SPREAD_BPS", "25"))


# ─── Data Models ────────────────────────────────────────────────────────────────
class FXQuote(BaseModel):
    quote_id: str
    base_currency: str = "INR"
    quote_currency: str = "USDC"
    mid_rate: float
    spread_bps: int
    buy_rate: float
    sell_rate: float
    source: str
    fetched_at: str
    expires_at: str
    session_id: str | None = None


class FXConversion(BaseModel):
    inr_amount: float
    usdc_amount: float
    rate_used: float
    quote_id: str
    converted_at: str


# ─── FXEngine ───────────────────────────────────────────────────────────────────
class FXEngine:
    """Live FX rate engine with caching, locking, and conversion."""

    FRANKFURTER_URL = "https://api.frankfurter.app/latest"

    async def fetch_live_rate(
        self,
        db_session: AsyncSession | None = None,
    ) -> FXQuote:
        """
        Fetch live INR/USD rate from Frankfurter API (free, no key).
        Returns: { "rates": { "INR": 84.xx } }
        mid_rate = 1 / rates["INR"]  (USD per INR ≈ USDC per INR)
        Phase 4: When db_session is provided, INSERT quote into fx_quotes table.
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=FX_CACHE_TTL_SECONDS)
        quote_id = str(uuid.uuid4())

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.FRANKFURTER_URL,
                    params={"from": "USD", "to": "INR"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        inr_per_usd = data.get("rates", {}).get("INR")
                        if inr_per_usd and inr_per_usd > 0:
                            mid_rate = 1.0 / inr_per_usd
                            source = "frankfurter"
                            logger.info(
                                "FX rate fetched: 1 INR = %.8f USDC "
                                "(1 USD = %.2f INR)", mid_rate, inr_per_usd,
                            )
                        else:
                            raise ValueError(f"Invalid INR rate: {inr_per_usd}")
                    else:
                        raise aiohttp.ClientError(
                            f"Frankfurter returned {resp.status}"
                        )
        except Exception as e:
            logger.warning("FX fetch failed (%s), using fallback rate", e)
            mid_rate = FX_FALLBACK_RATE
            source = "fallback"

        buy_rate = mid_rate * (1 - FX_SPREAD_BPS / 10000)
        sell_rate = mid_rate * (1 + FX_SPREAD_BPS / 10000)

        quote = FXQuote(
            quote_id=quote_id,
            base_currency="INR",
            quote_currency="USDC",
            mid_rate=round(mid_rate, 8),
            spread_bps=FX_SPREAD_BPS,
            buy_rate=round(buy_rate, 8),
            sell_rate=round(sell_rate, 8),
            source=source,
            fetched_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )

        # Phase 4: Persist to DB when db_session provided
        if db_session:
            expires_dt = datetime.fromisoformat(expires.isoformat().replace("Z", "+00:00"))
            db_fx = FxQuoteModel(
                quote_id=uuid.UUID(quote.quote_id),
                base_currency=quote.base_currency,
                quote_currency=quote.quote_currency,
                mid_rate=quote.mid_rate,
                buy_rate=quote.buy_rate,
                sell_rate=quote.sell_rate,
                spread_bps=quote.spread_bps,
                source=quote.source,
                fetched_at=now,
                expires_at=expires_dt,
                session_id=None,
            )
            db_session.add(db_fx)
            await db_session.flush()

        return quote

    async def get_rate(self, redis_client, db_session: AsyncSession) -> FXQuote:
        """Returns cached FX rate if not expired, else fetches new."""
        # Check Redis cache
        if redis_client:
            cached = await redis_client.get("fx:inr_usdc")
            if cached:
                try:
                    data = json.loads(cached)
                    quote = FXQuote(**data)
                    # Check expiry
                    exp = datetime.fromisoformat(quote.expires_at)
                    if exp > datetime.now(timezone.utc):
                        return quote
                except Exception:
                    pass

        # Fetch new rate (persists to DB when db_session provided)
        quote = await self.fetch_live_rate(db_session=db_session)

        # Cache in Redis
        if redis_client:
            await redis_client.set(
                "fx:inr_usdc",
                quote.model_dump_json(),
                ex=FX_CACHE_TTL_SECONDS,
            )

        return quote

    async def lock_rate_for_session(
        self,
        session_id: str,
        redis_client,
        db_session: AsyncSession,
    ) -> FXQuote:
        """
        Fetch current rate and lock it to a session.
        No TTL — lives for session lifetime.
        RULE 17: This rate NEVER changes once locked.
        """
        quote = await self.get_rate(redis_client, db_session)
        quote.session_id = session_id

        # Store session-specific lock in Redis (no TTL)
        if redis_client:
            await redis_client.set(
                f"fx:session:{session_id}",
                quote.model_dump_json(),
            )

        # Update DB record with session_id
        result = await db_session.execute(
            select(FxQuoteModel).where(
                FxQuoteModel.quote_id == uuid.UUID(quote.quote_id)
            )
        )
        db_row = result.scalar_one_or_none()
        if db_row:
            db_row.session_id = uuid.UUID(session_id)
            await db_session.flush()

        logger.info(
            "FX rate locked for session %s: sell_rate=%.8f source=%s",
            session_id[:8], quote.sell_rate, quote.source,
        )
        return quote

    async def get_session_rate(
        self, session_id: str, redis_client
    ) -> FXQuote:
        """Returns the FX rate locked to this session."""
        if redis_client:
            cached = await redis_client.get(f"fx:session:{session_id}")
            if cached:
                return FXQuote(**json.loads(cached))

        raise ValueError(f"No FX rate locked for session {session_id}")

    def convert_inr_to_usdc(
        self, inr_amount: float, quote: FXQuote
    ) -> FXConversion:
        """
        Convert INR to USDC using sell_rate.
        (Platform sells USD to buyer = less favorable rate.)
        """
        usdc_amount = round(inr_amount * quote.sell_rate, 6)
        return FXConversion(
            inr_amount=inr_amount,
            usdc_amount=usdc_amount,
            rate_used=quote.sell_rate,
            quote_id=quote.quote_id,
            converted_at=datetime.now(timezone.utc).isoformat(),
        )

    def convert_usdc_to_inr(
        self, usdc_amount: float, quote: FXQuote
    ) -> FXConversion:
        """
        Convert USDC to INR using buy_rate.
        """
        inr_amount = round(usdc_amount / quote.buy_rate, 2) if quote.buy_rate else 0.0
        return FXConversion(
            inr_amount=inr_amount,
            usdc_amount=usdc_amount,
            rate_used=quote.buy_rate,
            quote_id=quote.quote_id,
            converted_at=datetime.now(timezone.utc).isoformat(),
        )

    async def get_fx_history(
        self, limit: int = 50, db_session: AsyncSession | None = None
    ) -> list[dict]:
        """Returns last N FX quotes from DB."""
        if not db_session:
            return []
        result = await db_session.execute(
            select(FxQuoteModel)
            .order_by(FxQuoteModel.fetched_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "quote_id": str(r.quote_id),
                "mid_rate": float(r.mid_rate),
                "buy_rate": float(r.buy_rate),
                "sell_rate": float(r.sell_rate),
                "spread_bps": r.spread_bps,
                "source": r.source,
                "session_id": str(r.session_id) if r.session_id else None,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            }
            for r in rows
        ]


# Module-level singleton
fx_engine = FXEngine()
