"""
api/schemas/audit.py — Audit log + transcript Pydantic models.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    log_id: str
    entity_type: str
    action: str
    actor_id: str
    timestamp: str
    payload: Optional[dict] = None


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


class TranscriptEntry(BaseModel):
    log_id: str
    entity_type: str
    action: str
    actor_id: str
    timestamp: str
    prev_hash: str
    this_hash: str
    payload: Optional[dict] = None


class SessionTranscript(BaseModel):
    session_id: str
    exported_at: str
    chain_valid: bool
    entry_count: int
    entries: list[TranscriptEntry]


class ChainVerificationResult(BaseModel):
    valid: bool
    total_entries: int
    broken_at_log_id: Optional[str] = None
    broken_at_timestamp: Optional[str] = None
    verification_completed_at: str
