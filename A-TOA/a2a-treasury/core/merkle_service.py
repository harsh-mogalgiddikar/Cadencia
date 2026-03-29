"""
MerkleService — computes and stores Merkle root for a completed session.
Called automatically when a session reaches a terminal state.
Layer: Verification Layer — Agentic Commerce Framework
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.merkle import MerkleTree
from db.models import AuditLog, Negotiation

logger = logging.getLogger("a2a_treasury")


class MerkleService:
    """Compute, store, and retrieve Merkle roots for negotiation sessions."""

    @staticmethod
    async def compute_and_store(session_id: str, db: AsyncSession) -> str | None:
        """Compute Merkle root from a session's audit hashes and store it.

        Returns the hex root string, or None if no audit entries exist.
        """
        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id

        # 1. Query all AuditLog entries for this session, ordered by timestamp
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == sid)
            .order_by(AuditLog.timestamp.asc(), AuditLog.this_hash.asc()),
        )
        entries = result.scalars().all()

        # 2. Extract this_hash from each entry
        hashes = [entry.this_hash for entry in entries]

        if not hashes:
            return None

        # 3. Build Merkle tree
        tree = MerkleTree(hashes)
        root = tree.get_root()

        # 4. Update the Negotiation record with the merkle_root
        neg_result = await db.execute(
            select(Negotiation).where(Negotiation.session_id == sid),
        )
        neg = neg_result.scalar_one_or_none()
        if neg:
            neg.merkle_root = root
            await db.flush()

        logger.info(
            "Merkle root computed for session %s: %s... (%d leaves)",
            str(session_id)[:8],
            root[:16],
            len(hashes),
        )
        return root

    @staticmethod
    async def get_session_merkle(session_id: str, db: AsyncSession) -> dict | None:
        """Retrieve Merkle info for a session.

        Returns None if session not found or merkle_root is null.
        """
        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id

        result = await db.execute(
            select(Negotiation).where(Negotiation.session_id == sid),
        )
        neg = result.scalar_one_or_none()
        if neg is None or neg.merkle_root is None:
            return None

        # Count audit leaves
        count_result = await db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == sid)
            .order_by(AuditLog.timestamp.asc()),
        )
        entries = count_result.scalars().all()

        return {
            "session_id": str(session_id),
            "merkle_root": neg.merkle_root,
            "leaf_count": len(entries),
            "anchor_tx_id": neg.anchor_tx_id,
            "anchored_on_chain": neg.anchor_tx_id is not None,
        }
