"""Phase 4: FX engine tests."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.fx_engine import FXEngine, FXQuote, FX_SPREAD_BPS, FX_FALLBACK_RATE


@pytest.mark.asyncio
async def test_fetch_live_rate_returns_valid_quote():
    """With mocked successful HTTP response, quote has correct mid/buy/sell and source."""
    class MockResp:
        status = 200
        async def json(self):
            return {"rates": {"INR": 84.5}}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass

    with patch("core.fx_engine.aiohttp.ClientSession") as Session:
        session_instance = AsyncMock()
        session_instance.get = lambda *a, **k: MockResp()
        session_instance.__aenter__ = AsyncMock(return_value=session_instance)
        session_instance.__aexit__ = AsyncMock(return_value=None)
        Session.return_value = session_instance

        engine = FXEngine()
        quote = await engine.fetch_live_rate()
        assert quote.mid_rate == pytest.approx(1 / 84.5, rel=1e-6)
        assert quote.buy_rate < quote.mid_rate < quote.sell_rate
        assert quote.source == "frankfurter"
        uuid.UUID(quote.quote_id)


@pytest.mark.asyncio
async def test_fallback_rate_on_network_error():
    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
        engine = FXEngine()
        quote = await engine.fetch_live_rate()
        assert quote.source == "fallback"
        assert quote.mid_rate == FX_FALLBACK_RATE


def test_spread_applied_correctly():
    mid = 0.01193
    spread_bps = 25
    buy_rate = mid * (1 - spread_bps / 10000)
    sell_rate = mid * (1 + spread_bps / 10000)
    assert buy_rate == pytest.approx(0.01193 * (1 - 25 / 10000))
    assert sell_rate == pytest.approx(0.01193 * (1 + 25 / 10000))


def test_convert_inr_to_usdc_uses_sell_rate():
    engine = FXEngine()
    quote = FXQuote(quote_id=str(uuid.uuid4()), base_currency="INR", quote_currency="USDC",
                    mid_rate=0.012, spread_bps=25, buy_rate=0.01185, sell_rate=0.01200,
                    source="test", fetched_at="", expires_at="")
    conv = engine.convert_inr_to_usdc(100000, quote)
    assert conv.usdc_amount == pytest.approx(100000 * 0.01200)


def test_convert_usdc_to_inr_uses_buy_rate():
    engine = FXEngine()
    quote = FXQuote(quote_id=str(uuid.uuid4()), base_currency="INR", quote_currency="USDC",
                    mid_rate=0.012, spread_bps=25, buy_rate=0.01185, sell_rate=0.01200,
                    source="test", fetched_at="", expires_at="")
    conv = engine.convert_usdc_to_inr(1193, quote)
    assert conv.inr_amount == pytest.approx(1193 / 0.01185)
