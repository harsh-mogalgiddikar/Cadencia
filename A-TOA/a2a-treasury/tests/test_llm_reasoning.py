"""
tests/test_llm_reasoning.py — Phase 2 LLM Advisory tests.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch

from core.llm_reasoning import (
    LLMAdvisory,
    DEFAULT_ADVISORY,
    GeminiAdvisor,
    _cap_modifier,
)


def test_default_advisory_fallback_used():
    assert DEFAULT_ADVISORY.fallback_used is True
    assert DEFAULT_ADVISORY.recommended_modifier == 0.0


def test_cap_modifier():
    assert _cap_modifier(0.6) == 0.5
    assert _cap_modifier(-0.6) == -0.5
    assert _cap_modifier(0.2) == 0.2


@pytest.mark.asyncio
async def test_returns_default_when_llm_disabled():
    with patch.dict(os.environ, {"LLM_ENABLED": "false"}):
        from importlib import reload
        import core.llm_reasoning as m
        reload(m)
        advisor = m.GeminiAdvisor()
        out = await advisor.classify_opponent(
            [], {"current_round": 1, "max_rounds": 8, "agent_role": "buyer"}, {}, ""
        )
        assert out.fallback_used or out.recommended_modifier == 0.0
    with patch.dict(os.environ, {"LLM_ENABLED": "true"}):
        reload(m)


@pytest.mark.asyncio
async def test_returns_default_on_api_failure():
    advisor = GeminiAdvisor()
    with patch.object(advisor, "_session_circuit_open", return_value=False):
        with patch("core.llm_reasoning._gemini_generate", AsyncMock(return_value=None)):
            out = await advisor.classify_opponent(
                [{"round": 1, "agent_role": "seller", "value": 90, "action": "counter"}],
                {"current_round": 2, "max_rounds": 8, "agent_role": "buyer"},
                {"pattern": "strategic"},
                "session-1",
            )
            assert out.fallback_used or out.recommended_modifier == 0.0
