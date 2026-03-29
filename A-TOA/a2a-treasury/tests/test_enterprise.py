"""
tests/test_enterprise.py — Tests for enterprise registration and agent card.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from a2a_protocol.agent_card import generate_agent_card
from db.models import Enterprise
from tests.conftest import create_enterprise


class TestEnterpriseLifecycle:
    @pytest_asyncio.fixture
    async def pending_enterprise(self, db_session):
        return await create_enterprise(db_session, "Test Ltd", "PENDING")

    @pytest_asyncio.fixture
    async def verified_enterprise(self, db_session):
        return await create_enterprise(db_session, "Verified Ltd", "EMAIL_VERIFIED")

    @pytest.mark.asyncio
    async def test_enterprise_creation(self, pending_enterprise):
        assert pending_enterprise.kyc_status == "PENDING"
        assert pending_enterprise.legal_name == "Test Ltd"

    @pytest.mark.asyncio
    async def test_email_verification_transition(self, db_session, pending_enterprise):
        await db_session.execute(
            update(Enterprise)
            .where(Enterprise.enterprise_id == pending_enterprise.enterprise_id)
            .values(kyc_status="EMAIL_VERIFIED"),
        )
        await db_session.flush()

        result = await db_session.execute(
            select(Enterprise).where(
                Enterprise.enterprise_id == pending_enterprise.enterprise_id,
            ),
        )
        ent = result.scalar_one()
        assert ent.kyc_status == "EMAIL_VERIFIED"

    @pytest.mark.asyncio
    async def test_activation_transition(self, db_session, verified_enterprise):
        await db_session.execute(
            update(Enterprise)
            .where(Enterprise.enterprise_id == verified_enterprise.enterprise_id)
            .values(kyc_status="ACTIVE"),
        )
        await db_session.flush()

        result = await db_session.execute(
            select(Enterprise).where(
                Enterprise.enterprise_id == verified_enterprise.enterprise_id,
            ),
        )
        ent = result.scalar_one()
        assert ent.kyc_status == "ACTIVE"


class TestAgentCard:
    def test_agent_card_generation(self):
        eid = str(uuid.uuid4())
        card = generate_agent_card(eid, "Test Corp")
        assert card["name"] == "Test Corp Trade Agent"
        assert card["version"] == "1.0"
        assert card["enterpriseId"] == eid
        assert card["kycStatus"] == "ACTIVE"
        assert len(card["skills"]) == 1
        assert card["skills"][0]["id"] == "price-negotiation"
        assert "agentCardGeneratedAt" in card

    def test_agent_card_capabilities(self):
        card = generate_agent_card(str(uuid.uuid4()), "Cap Test")
        caps = card["capabilities"]
        assert caps["streaming"] is False
        assert caps["pushNotifications"] is True
        assert caps["stateTransitionHistory"] is True

    @pytest.mark.asyncio
    async def test_agent_card_stored_on_activation(self, db_session):
        ent = await create_enterprise(db_session, "Card Test Ltd", "EMAIL_VERIFIED")
        card = generate_agent_card(str(ent.enterprise_id), ent.legal_name)

        await db_session.execute(
            update(Enterprise)
            .where(Enterprise.enterprise_id == ent.enterprise_id)
            .values(
                kyc_status="ACTIVE",
                agent_card_data=card,
                agent_card_url=f"/enterprises/{ent.enterprise_id}/.well-known/agent.json",
            ),
        )
        await db_session.flush()

        result = await db_session.execute(
            select(Enterprise).where(
                Enterprise.enterprise_id == ent.enterprise_id,
            ),
        )
        updated = result.scalar_one()
        assert updated.agent_card_data is not None
        assert updated.agent_card_data["name"] == "Card Test Ltd Trade Agent"
        assert updated.agent_card_url is not None
