"""
tests/test_audit_logger.py — Tests for SHA-256 hash-chained audit logger.
"""
from __future__ import annotations

import hashlib
import json
import uuid

import pytest
import pytest_asyncio

from db.audit_logger import AuditLogger
from db.models import AuditLog


@pytest.fixture
def audit_logger():
    return AuditLogger()


class TestHashChain:
    @pytest.mark.asyncio
    async def test_first_entry_uses_genesis(self, audit_logger, db_session):
        entry = await audit_logger.append(
            entity_type="test",
            entity_id=str(uuid.uuid4()),
            action="TEST_ACTION",
            actor_id="tester",
            payload={"key": "value"},
            db_session=db_session,
        )
        assert entry.prev_hash == "genesis"
        assert len(entry.this_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_chain_valid_after_10_appends(self, audit_logger, db_session):
        entity_id = str(uuid.uuid4())
        for i in range(10):
            await audit_logger.append(
                entity_type="test",
                entity_id=entity_id,
                action=f"ACTION_{i}",
                actor_id="tester",
                payload={"index": i},
                db_session=db_session,
            )

        result = await audit_logger.verify_chain(db_session)
        assert result["valid"] is True
        assert result["total_entries"] == 10

    @pytest.mark.asyncio
    async def test_chain_linkage(self, audit_logger, db_session):
        entity_id = str(uuid.uuid4())
        entry1 = await audit_logger.append(
            entity_type="test",
            entity_id=entity_id,
            action="FIRST",
            actor_id="tester",
            payload={"seq": 1},
            db_session=db_session,
        )
        entry2 = await audit_logger.append(
            entity_type="test",
            entity_id=entity_id,
            action="SECOND",
            actor_id="tester",
            payload={"seq": 2},
            db_session=db_session,
        )

        assert entry2.prev_hash == entry1.this_hash


class TestSessionTranscript:
    @pytest.mark.asyncio
    async def test_export_transcript(self, audit_logger, db_session):
        session_id = uuid.uuid4()
        for i in range(3):
            await audit_logger.append(
                entity_type="negotiation",
                entity_id=str(session_id),
                action=f"SESSION_EVENT_{i}",
                actor_id="system",
                payload={"round": i},
                db_session=db_session,
            )

        transcript = await audit_logger.export_session_transcript(
            str(session_id), db_session,
        )
        assert transcript["session_id"] == str(session_id)
        assert transcript["entry_count"] == 3
        assert transcript["chain_valid"] is True
        assert len(transcript["entries"]) == 3


class TestEnterpriseLog:
    @pytest.mark.asyncio
    async def test_paginated_log(self, audit_logger, db_session):
        enterprise_id = uuid.uuid4()
        for i in range(5):
            await audit_logger.append(
                entity_type="enterprise",
                entity_id=str(enterprise_id),
                action=f"EVENT_{i}",
                actor_id="admin",
                payload={},
                db_session=db_session,
            )

        result = await audit_logger.get_enterprise_log(
            str(enterprise_id), page=1, page_size=3, db_session=db_session,
        )
        assert result["total"] == 5
        assert len(result["items"]) == 3
        assert result["page"] == 1
