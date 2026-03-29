"""
tests/test_state_machine.py — Tests for DANP State Machine.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from core.state_machine import DANPStateMachine, TERMINAL_STATES
from db.models import Enterprise, Negotiation, Offer
from tests.conftest import (
    FakeRedisSessionManager,
    create_agent_config,
    create_enterprise,
    create_treasury_policy,
    create_user,
)


@pytest.fixture
def state_machine():
    return DANPStateMachine()


@pytest.fixture
def fake_redis():
    return FakeRedisSessionManager()


@pytest_asyncio.fixture
async def buyer_enterprise(db_session):
    return await create_enterprise(db_session, "Mumbai Imports Ltd", "ACTIVE")


@pytest_asyncio.fixture
async def seller_enterprise(db_session):
    return await create_enterprise(db_session, "Ravi Exports Pvt Ltd", "ACTIVE")


@pytest_asyncio.fixture
async def buyer_config(db_session, buyer_enterprise):
    return await create_agent_config(
        db_session, buyer_enterprise.enterprise_id,
        agent_role="buyer", intrinsic_value=92000.0, risk_factor=0.12,
        negotiation_margin=0.08, budget_ceiling=96000.0,
    )


@pytest_asyncio.fixture
async def seller_config(db_session, seller_enterprise):
    return await create_agent_config(
        db_session, seller_enterprise.enterprise_id,
        agent_role="seller", intrinsic_value=87000.0, risk_factor=0.06,
        negotiation_margin=0.05, budget_ceiling=None,
    )


@pytest_asyncio.fixture
async def buyer_policy(db_session, buyer_enterprise):
    return await create_treasury_policy(db_session, buyer_enterprise.enterprise_id)


@pytest_asyncio.fixture
async def seller_policy(db_session, seller_enterprise):
    return await create_treasury_policy(db_session, seller_enterprise.enterprise_id)


class TestSessionCreation:
    @pytest.mark.asyncio
    async def test_create_session_success(
        self, state_machine, db_session, fake_redis,
        buyer_enterprise, seller_enterprise, buyer_config, seller_config,
        buyer_policy, seller_policy,
    ):
        result = await state_machine.create_session(
            buyer_enterprise_id=str(buyer_enterprise.enterprise_id),
            seller_enterprise_id=str(seller_enterprise.enterprise_id),
            initial_offer_value=85000.0,
            milestone_template_id="tmpl-single-delivery",
            timeout_seconds=3600,
            max_rounds=8,
            db_session=db_session,
            redis_client=fake_redis,
        )

        assert result["status"] == "BUYER_ANCHOR"
        assert result["max_rounds"] == 8
        assert "session_id" in result

        # Verify Redis write
        state = await fake_redis.get_session_state(result["session_id"])
        assert state is not None
        assert state["status"] == "BUYER_ANCHOR"

        # Verify PostgreSQL write
        neg = (await db_session.execute(
            select(Negotiation).where(
                Negotiation.session_id == uuid.UUID(result["session_id"]),
            ),
        )).scalar_one()
        assert neg.status == "BUYER_ANCHOR"

    @pytest.mark.asyncio
    async def test_create_session_same_enterprise_fails(
        self, state_machine, db_session, fake_redis,
        buyer_enterprise, buyer_config, buyer_policy,
    ):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await state_machine.create_session(
                buyer_enterprise_id=str(buyer_enterprise.enterprise_id),
                seller_enterprise_id=str(buyer_enterprise.enterprise_id),
                initial_offer_value=85000.0,
                milestone_template_id="tmpl-single-delivery",
                timeout_seconds=3600,
                max_rounds=8,
                db_session=db_session,
                redis_client=fake_redis,
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_session_exceeds_budget_ceiling(
        self, state_machine, db_session, fake_redis,
        buyer_enterprise, seller_enterprise, buyer_config, seller_config,
        buyer_policy, seller_policy,
    ):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await state_machine.create_session(
                buyer_enterprise_id=str(buyer_enterprise.enterprise_id),
                seller_enterprise_id=str(seller_enterprise.enterprise_id),
                initial_offer_value=97000.0,  # exceeds 96000 ceiling
                milestone_template_id="tmpl-single-delivery",
                timeout_seconds=3600,
                max_rounds=8,
                db_session=db_session,
                redis_client=fake_redis,
            )
        assert exc_info.value.status_code == 422


class TestProcessAction:
    @pytest.mark.asyncio
    async def test_walkaway_on_reject(
        self, state_machine, db_session, fake_redis,
        buyer_enterprise, seller_enterprise, buyer_config, seller_config,
        buyer_policy, seller_policy,
    ):
        session = await state_machine.create_session(
            buyer_enterprise_id=str(buyer_enterprise.enterprise_id),
            seller_enterprise_id=str(seller_enterprise.enterprise_id),
            initial_offer_value=85000.0,
            milestone_template_id="tmpl-single-delivery",
            timeout_seconds=3600,
            max_rounds=8,
            db_session=db_session,
            redis_client=fake_redis,
        )

        # Seller rejects
        result = await state_machine.process_action(
            action={
                "session_id": session["session_id"],
                "agent_role": "seller",
                "round": 1,
                "action": "reject",
                "offer_value": None,
                "confidence": 0.9,
                "strategy_tag": None,
                "rationale": "Price too low",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            db_session=db_session,
            redis_client=fake_redis,
        )

        assert result["status"] == "WALKAWAY"
        assert result["is_terminal"] is True

    @pytest.mark.asyncio
    async def test_turn_violation(
        self, state_machine, db_session, fake_redis,
        buyer_enterprise, seller_enterprise, buyer_config, seller_config,
        buyer_policy, seller_policy,
    ):
        session = await state_machine.create_session(
            buyer_enterprise_id=str(buyer_enterprise.enterprise_id),
            seller_enterprise_id=str(seller_enterprise.enterprise_id),
            initial_offer_value=85000.0,
            milestone_template_id="tmpl-single-delivery",
            timeout_seconds=3600,
            max_rounds=8,
            db_session=db_session,
            redis_client=fake_redis,
        )

        # Buyer trying to go again (should be seller's turn)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await state_machine.process_action(
                action={
                    "session_id": session["session_id"],
                    "agent_role": "buyer",
                    "round": 1,
                    "action": "counter",
                    "offer_value": 86000.0,
                    "confidence": 0.9,
                    "strategy_tag": "concede",
                    "rationale": None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                db_session=db_session,
                redis_client=fake_redis,
            )
        assert exc_info.value.status_code == 409
