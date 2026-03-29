"""
api/routes/audit.py — Audit log, transcript, and Merkle verification endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import UserContext, require_any_role
from db.audit_logger import AuditLogger
from db.database import get_db

router = APIRouter(prefix="/audit", tags=["Audit"])
audit_logger = AuditLogger()


@router.get("/{enterprise_id}/log")
async def get_enterprise_audit_log(
    enterprise_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated audit log for an enterprise."""
    return await audit_logger.get_enterprise_log(
        enterprise_id=enterprise_id,
        page=page,
        page_size=page_size,
        db_session=db,
    )


@router.get("/verify-chain")
async def verify_audit_chain(
    session_id: str | None = Query(None, description="Scope verification to a specific session"),
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Verify the audit log hash chain, optionally scoped to a session."""
    return await audit_logger.verify_chain(db, session_id=session_id)


# ─── Phase 3 ACF: Merkle verification endpoints ────────────────────────────

@router.get("/{session_id}/merkle")
async def get_session_merkle(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the Merkle root and proof info for a session.

    - 200: Merkle info available
    - 202: Session exists but merkle_root not yet computed (pending)
    - 404: Session not found
    """
    import uuid
    from sqlalchemy import select
    from db.models import Negotiation

    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return {"error": "INVALID_SESSION_ID"}, 400

    # Check if session exists
    result = await db.execute(
        select(Negotiation).where(Negotiation.session_id == sid),
    )
    neg = result.scalar_one_or_none()

    if neg is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "SESSION_NOT_FOUND"})

    if neg.merkle_root is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content={"status": "pending"})

    from core.merkle_service import MerkleService
    merkle_data = await MerkleService.get_session_merkle(session_id, db)
    if merkle_data is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=202, content={"status": "pending"})

    # Build verification URL
    verification_url = None
    if merkle_data.get("anchor_tx_id") and not merkle_data["anchor_tx_id"].startswith("SIM-"):
        verification_url = (
            f"https://lora.algokit.io/testnet/transaction/{merkle_data['anchor_tx_id']}"
        )

    return {
        "session_id": session_id,
        "merkle_root": merkle_data["merkle_root"],
        "leaf_count": merkle_data["leaf_count"],
        "anchor_tx_id": merkle_data.get("anchor_tx_id"),
        "anchored_on_chain": merkle_data.get("anchored_on_chain", False),
        "verification_url": verification_url,
    }


class VerifyLeafRequest(BaseModel):
    leaf_hash: str


@router.post("/{session_id}/verify-leaf")
async def verify_leaf(
    session_id: str,
    body: VerifyLeafRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify that a specific audit entry is part of the session's Merkle tree.

    Returns the proof path and verification result.
    """
    import uuid
    from sqlalchemy import select
    from db.models import AuditLog, Negotiation
    from core.merkle import MerkleTree
    from fastapi.responses import JSONResponse

    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "INVALID_SESSION_ID"})

    # Check session exists and has merkle_root
    neg_result = await db.execute(
        select(Negotiation).where(Negotiation.session_id == sid),
    )
    neg = neg_result.scalar_one_or_none()
    if neg is None:
        return JSONResponse(status_code=404, content={"error": "SESSION_NOT_FOUND"})

    # Load all audit hashes for session
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == sid)
        .order_by(AuditLog.timestamp.asc(), AuditLog.this_hash.asc()),
    )
    entries = result.scalars().all()
    hashes = [entry.this_hash for entry in entries]

    if not hashes:
        return JSONResponse(status_code=404, content={"error": "NO_AUDIT_ENTRIES"})

    # Build tree and get proof
    tree = MerkleTree(hashes)
    proof = tree.get_proof(body.leaf_hash)

    if proof is None:
        return JSONResponse(status_code=404, content={"error": "LEAF_NOT_FOUND"})

    # Verify against stored merkle_root (or computed root)
    stored_root = neg.merkle_root or tree.get_root()
    verified = tree.verify(body.leaf_hash, proof)

    return {
        "leaf_hash": body.leaf_hash,
        "merkle_root": stored_root,
        "proof": proof,
        "verified": verified,
    }
