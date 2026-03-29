"""
tests/test_guardrails.py — Tests for Layer 4 Guardrail Engine.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from core.guardrails import GuardrailEngine, GuardrailResult


@pytest.fixture
def engine():
    return GuardrailEngine()


@pytest.fixture
def seller_snapshot():
    return {
        "reservation_price": 81780.0,
        "target_price": 91350.0,
        "agent_role": "seller",
    }


@pytest.fixture
def buyer_snapshot():
    return {
        "reservation_price": 103040.0,
        "target_price": 84640.0,
        "agent_role": "buyer",
    }


@pytest.fixture
def buyer_config():
    return {
        "budget_ceiling": 96000.0,
        "max_exposure": 100000.0,
        "agent_role": "buyer",
    }


@pytest.fixture
def seller_config():
    return {
        "budget_ceiling": None,
        "max_exposure": 100000.0,
        "agent_role": "seller",
    }


@pytest.fixture
def session_state():
    return {"status": "ROUND_LOOP", "current_round": 3}


class TestReservationBreach:
    def test_seller_offer_below_reservation_blocked(
        self, engine, seller_snapshot, seller_config, session_state,
    ):
        action = {"agent_role": "seller", "action": "counter", "offer_value": 80000.0}
        result = engine.validate_action(action, seller_snapshot, seller_config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "RESERVATION_BREACH"

    def test_seller_offer_above_reservation_cleared(
        self, engine, seller_snapshot, seller_config, session_state,
    ):
        action = {"agent_role": "seller", "action": "counter", "offer_value": 85000.0}
        result = engine.validate_action(action, seller_snapshot, seller_config, session_state)
        assert result.status == "CLEARED"


class TestBudgetCeilingBreach:
    def test_buyer_offer_above_ceiling_blocked(
        self, engine, buyer_snapshot, buyer_config, session_state,
    ):
        action = {"agent_role": "buyer", "action": "counter", "offer_value": 97000.0}
        result = engine.validate_action(action, buyer_snapshot, buyer_config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "BUDGET_CEILING_BREACH"

    def test_buyer_offer_below_ceiling_cleared(
        self, engine, buyer_snapshot, buyer_config, session_state,
    ):
        action = {"agent_role": "buyer", "action": "counter", "offer_value": 90000.0}
        result = engine.validate_action(action, buyer_snapshot, buyer_config, session_state)
        assert result.status == "CLEARED"


class TestMaxExposureBreach:
    def test_offer_above_max_exposure_blocked(
        self, engine, buyer_snapshot, session_state,
    ):
        config = {"budget_ceiling": 200000.0, "max_exposure": 100000.0}
        action = {"agent_role": "buyer", "action": "counter", "offer_value": 150000.0}
        result = engine.validate_action(action, buyer_snapshot, config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "MAX_EXPOSURE_BREACH"


class TestAcceptBelowFloor:
    def test_seller_accept_below_floor_blocked(
        self, engine, seller_snapshot, seller_config, session_state,
    ):
        action = {"agent_role": "seller", "action": "accept", "offer_value": 75000.0}
        result = engine.validate_action(action, seller_snapshot, seller_config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "ACCEPT_BELOW_FLOOR"


class TestAcceptAboveCeiling:
    def test_buyer_accept_above_ceiling_blocked(
        self, engine, buyer_snapshot, buyer_config, session_state,
    ):
        action = {"agent_role": "buyer", "action": "accept", "offer_value": 97000.0}
        result = engine.validate_action(action, buyer_snapshot, buyer_config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "ACCEPT_ABOVE_CEILING"


class TestInvalidOfferValue:
    def test_zero_offer_blocked(
        self, engine, buyer_snapshot, buyer_config, session_state,
    ):
        action = {"agent_role": "buyer", "action": "counter", "offer_value": 0.0}
        result = engine.validate_action(action, buyer_snapshot, buyer_config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "INVALID_OFFER_VALUE"

    def test_negative_offer_blocked(
        self, engine, buyer_snapshot, buyer_config, session_state,
    ):
        action = {"agent_role": "buyer", "action": "counter", "offer_value": -500.0}
        result = engine.validate_action(action, buyer_snapshot, buyer_config, session_state)
        assert result.status == "BLOCKED"
        assert result.rule_violated == "INVALID_OFFER_VALUE"


class TestAllChecksPassed:
    def test_valid_buyer_counter_cleared(
        self, engine, buyer_snapshot, buyer_config, session_state,
    ):
        action = {"agent_role": "buyer", "action": "counter", "offer_value": 90000.0}
        result = engine.validate_action(action, buyer_snapshot, buyer_config, session_state)
        assert result.status == "CLEARED"
        assert result.message == "All checks passed"

    def test_valid_seller_counter_cleared(
        self, engine, seller_snapshot, seller_config, session_state,
    ):
        action = {"agent_role": "seller", "action": "counter", "offer_value": 88000.0}
        result = engine.validate_action(action, seller_snapshot, seller_config, session_state)
        assert result.status == "CLEARED"
