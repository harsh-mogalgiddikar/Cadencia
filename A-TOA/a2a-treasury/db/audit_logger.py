"""
db/audit_logger.py — Append-only SHA-256 hash-chained audit logger.

Every write is permanent. No UPDATE. No DELETE. Compliance-grade.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog


class AuditLogger:
    """Append-only audit log with SHA-256 hash chaining."""

    @staticmethod
    def _normalize_ts(ts: datetime) -> str:
        """Normalize timestamp to a consistent string format for hashing.
        SQLite strips timezone info, so we always use naive UTC ISO format."""
        # Always strip tzinfo for consistent canonical string
        naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
        return naive.isoformat()

    async def append(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        payload: dict,
        db_session: AsyncSession,
    ) -> AuditLog:
        """
        Insert a new audit log entry with a cryptographic hash chain.

        Algorithm:
        1. Query DB for the most recent entry's this_hash as prev_hash
        2. Build canonical string for deterministic hashing
        3. Compute SHA-256
        4. INSERT new row

        Always queries DB (no in-memory cache) to ensure correctness
        when multiple AuditLogger instances write to the same chain.
        """
        # 1. Get prev_hash — always query DB for true latest
        result = await db_session.execute(
            select(AuditLog.this_hash, AuditLog.timestamp)
            .order_by(AuditLog.timestamp.desc(), AuditLog.this_hash.desc())
            .limit(1),
        )
        row = result.first()
        prev_hash = row[0] if row else "genesis"

        # 2. Timestamp
        timestamp_utc = datetime.now(timezone.utc)
        ts_str = self._normalize_ts(timestamp_utc)

        # 3. Build canonical string
        payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        canonical = (
            f"{entity_type}:{entity_id}:{action}:{actor_id}:"
            f"{ts_str}:{payload_str}:{prev_hash}"
        )

        # 4. Compute SHA-256
        this_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        # 5. INSERT
        entry = AuditLog(
            log_id=uuid.uuid4(),
            entity_type=entity_type,
            entity_id=uuid.UUID(str(entity_id)) if not isinstance(entity_id, uuid.UUID) else entity_id,
            action=action,
            actor_id=actor_id,
            timestamp=timestamp_utc,
            prev_hash=prev_hash,
            this_hash=this_hash,
            payload=payload,
        )
        db_session.add(entry)
        await db_session.flush()
        return entry

    async def verify_chain(self, db_session: AsyncSession, *, session_id: str | None = None) -> dict:
        """
        Verify hash chain integrity.

        If session_id is provided, verify only entries for that session
        (checks each entry's this_hash is correctly computed).
        If session_id is None, verify the global chain from genesis.
        """
        if session_id:
            return await self._verify_session_chain(session_id, db_session)

        result = await db_session.execute(select(AuditLog))
        all_entries = result.scalars().all()

        if not all_entries:
            return {
                "valid": True,
                "total_entries": 0,
                "broken_at_log_id": None,
                "broken_at_timestamp": None,
                "verification_completed_at": datetime.now(timezone.utc).isoformat(),
            }

        # Build lookup: prev_hash → entry (for following the chain)
        by_prev_hash: dict[str, AuditLog] = {}
        for entry in all_entries:
            by_prev_hash[entry.prev_hash] = entry

        # Walk the chain from genesis
        current_prev = "genesis"
        visited = 0
        while current_prev in by_prev_hash:
            entry = by_prev_hash[current_prev]
            visited += 1

            # Recompute hash to verify integrity
            ts_str = self._normalize_ts(entry.timestamp)
            payload_str = json.dumps(
                entry.payload or {}, sort_keys=True, separators=(",", ":"),
            )
            canonical = (
                f"{entry.entity_type}:{entry.entity_id}:{entry.action}:"
                f"{entry.actor_id}:{ts_str}:{payload_str}:{entry.prev_hash}"
            )
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

            if recomputed != entry.this_hash:
                return {
                    "valid": False,
                    "total_entries": len(all_entries),
                    "broken_at_log_id": str(entry.log_id),
                    "broken_at_timestamp": entry.timestamp.isoformat(),
                    "verification_completed_at": datetime.now(timezone.utc).isoformat(),
                }

            current_prev = entry.this_hash

        # Check we visited all entries
        if visited != len(all_entries):
            return {
                "valid": False,
                "total_entries": len(all_entries),
                "broken_at_log_id": None,
                "broken_at_timestamp": None,
                "verification_completed_at": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "valid": True,
            "total_entries": len(all_entries),
            "broken_at_log_id": None,
            "broken_at_timestamp": None,
            "verification_completed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _verify_session_chain(self, session_id: str, db_session: AsyncSession) -> dict:
        """
        Verify hash integrity for entries belonging to a specific session.
        Checks that each entry's this_hash was correctly computed from its fields.
        """
        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == sid)
            .order_by(AuditLog.timestamp.asc(), AuditLog.this_hash.asc()),
        )
        entries = result.scalars().all()

        if not entries:
            return {
                "valid": True,
                "total_entries": 0,
                "session_id": str(session_id),
                "broken_at_log_id": None,
                "broken_at_timestamp": None,
                "verification_completed_at": datetime.now(timezone.utc).isoformat(),
            }

        for entry in entries:
            ts_str = self._normalize_ts(entry.timestamp)
            payload_str = json.dumps(
                entry.payload or {}, sort_keys=True, separators=(",", ":"),
            )
            canonical = (
                f"{entry.entity_type}:{entry.entity_id}:{entry.action}:"
                f"{entry.actor_id}:{ts_str}:{payload_str}:{entry.prev_hash}"
            )
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

            if recomputed != entry.this_hash:
                return {
                    "valid": False,
                    "total_entries": len(entries),
                    "session_id": str(session_id),
                    "broken_at_log_id": str(entry.log_id),
                    "broken_at_timestamp": entry.timestamp.isoformat(),
                    "verification_completed_at": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "valid": True,
            "total_entries": len(entries),
            "session_id": str(session_id),
            "broken_at_log_id": None,
            "broken_at_timestamp": None,
            "verification_completed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def export_session_transcript(
        self, session_id: str, db_session: AsyncSession,
    ) -> dict:
        """
        Return all audit log entries related to a session.
        Walks the global chain in order, then filters entries
        belonging to this session (by entity_id or payload.session_id).
        """
        sid_str = str(session_id)
        sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id

        # Fetch ALL entries and walk the global chain
        result = await db_session.execute(select(AuditLog))
        all_entries = result.scalars().all()

        # Walk global chain from genesis
        by_prev: dict[str, AuditLog] = {}
        for entry in all_entries:
            by_prev[entry.prev_hash] = entry

        chain_ordered: list[AuditLog] = []
        current = by_prev.get("genesis")
        seen: set[str] = set()
        while current and current.this_hash not in seen:
            chain_ordered.append(current)
            seen.add(current.this_hash)
            current = by_prev.get(current.this_hash)

        # Filter to session-related entries
        def _belongs_to_session(e: AuditLog) -> bool:
            if e.entity_id == sid:
                return True
            # Check payload for session_id reference
            payload = e.payload or {}
            if payload.get("session_id") == sid_str:
                return True
            return False

        entries = [e for e in chain_ordered if _belongs_to_session(e)]

        # Verify each entry's hash integrity
        chain_valid = True
        for entry in entries:
            ts_str = self._normalize_ts(entry.timestamp)
            payload_str = json.dumps(
                entry.payload or {}, sort_keys=True, separators=(",", ":"),
            )
            canonical = (
                f"{entry.entity_type}:{entry.entity_id}:{entry.action}:"
                f"{entry.actor_id}:{ts_str}:{payload_str}:{entry.prev_hash}"
            )
            recomputed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if recomputed != entry.this_hash:
                chain_valid = False
                break

        return {
            "session_id": str(session_id),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "chain_valid": chain_valid,
            "entry_count": len(entries),
            "entries": [
                {
                    "log_id": str(e.log_id),
                    "entity_type": e.entity_type,
                    "action": e.action,
                    "actor_id": e.actor_id,
                    "timestamp": e.timestamp.isoformat(),
                    "prev_hash": e.prev_hash,
                    "this_hash": e.this_hash,
                    "payload": e.payload,
                }
                for e in entries
            ],
        }

    async def get_enterprise_log(
        self,
        enterprise_id: str,
        page: int,
        page_size: int,
        db_session: AsyncSession,
    ) -> dict:
        """Paginated audit log for an enterprise."""
        eid = uuid.UUID(enterprise_id) if isinstance(enterprise_id, str) else enterprise_id

        # Count total
        count_q = select(func.count(AuditLog.log_id)).where(
            AuditLog.entity_id == eid,
        )
        total = (await db_session.execute(count_q)).scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == eid)
            .order_by(AuditLog.timestamp.desc())
            .offset(offset)
            .limit(page_size),
        )
        entries = result.scalars().all()

        return {
            "items": [
                {
                    "log_id": str(e.log_id),
                    "entity_type": e.entity_type,
                    "action": e.action,
                    "actor_id": e.actor_id,
                    "timestamp": e.timestamp.isoformat(),
                    "payload": e.payload,
                }
                for e in entries
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
