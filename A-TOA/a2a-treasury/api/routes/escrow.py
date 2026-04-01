"""
api/routes/escrow.py — Escrow and milestone endpoints.

GET  /escrow/{session_id}           — escrow details by session
POST /escrow/{escrow_id}/release    — admin release (milestone)
POST /escrow/{escrow_id}/refund     — admin refund
GET  /escrow/{escrow_id}/status     — on-chain status
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from api.dependencies import UserContext, require_admin, require_any_role
from db.database import get_db
from db.models import EscrowContract

router = APIRouter(prefix="/escrow", tags=["Escrow"])


def _get_redis():
    from api.main import redis_manager
    return redis_manager


class ReleaseRequest(BaseModel):
    milestone: str = "milestone-1"


# ─── GET /escrow/session/{session_id} (escrow details by session) ─────────────
@router.get("/session/{session_id}")
async def get_escrow_by_session(
    session_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Returns escrow contract details for a session. 404 if none."""
    result = await db.execute(
        select(EscrowContract)
        .where(EscrowContract.session_id == uuid.UUID(session_id))
        .order_by(EscrowContract.deployed_at.desc())
        .limit(1),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "No escrow for this session")
    return {
        "escrow_id": str(row.escrow_id),
        "session_id": str(row.session_id),
        "contract_ref": row.contract_ref,
        "network_id": row.network_id,
        "amount": float(row.amount) if row.amount else None,
        "status": row.status,
        "deployed_at": row.deployed_at.isoformat() if row.deployed_at else None,
        "tx_ref": row.tx_ref,
    }


# ─── GET /escrow/{escrow_id} (by escrow id) ──────────────────────────────────
@router.get("/{escrow_id}")
async def get_escrow(
    escrow_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Returns escrow contract by escrow_id."""
    result = await db.execute(
        select(EscrowContract).where(
            EscrowContract.escrow_id == uuid.UUID(escrow_id),
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Escrow not found")
    return {
        "escrow_id": str(row.escrow_id),
        "session_id": str(row.session_id),
        "contract_ref": row.contract_ref,
        "network_id": row.network_id,
        "amount": float(row.amount) if row.amount else None,
        "status": row.status,
        "deployed_at": row.deployed_at.isoformat() if row.deployed_at else None,
        "tx_ref": row.tx_ref,
    }


# ─── POST /escrow/{escrow_id}/release ───────────────────────────────────────
@router.post("/{escrow_id}/release")
async def release_escrow(
    escrow_id: str,
    body: ReleaseRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 4: Release escrow to seller (milestone)."""
    redis = _get_redis()
    from blockchain.escrow_manager import EscrowManager
    manager = EscrowManager()
    result = await manager.release_escrow(
        escrow_id=escrow_id,
        milestone_description=body.milestone,
        db_session=db,
        redis_client=redis,
    )
    await db.commit()
    return result


# ─── POST /escrow/{escrow_id}/refund ────────────────────────────────────────
class RefundRequest(BaseModel):
    reason: str = "Dispute — refund"


@router.post("/{escrow_id}/refund")
async def refund_escrow(
    escrow_id: str,
    body: RefundRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 4: Refund escrow to buyer (dispute path)."""
    redis = _get_redis()
    from blockchain.escrow_manager import EscrowManager
    manager = EscrowManager()
    result = await manager.refund_escrow(
        escrow_id=escrow_id,
        reason=body.reason,
        db_session=db,
        redis_client=redis,
    )
    await db.commit()
    return result


# ─── POST /escrow/{escrow_id}/fund ───────────────────────────────────────────
@router.post("/{escrow_id}/fund")
async def fund_escrow(
    escrow_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 4: Fund escrow — transfer USDC from buyer to multisig. Idempotent."""
    redis = _get_redis()
    from blockchain.escrow_manager import EscrowManager
    manager = EscrowManager()
    result = await manager.fund_escrow(escrow_id, db, redis)
    await db.commit()
    return result


# ─── GET /escrow/{escrow_id}/status ──────────────────────────────────────────
@router.get("/{escrow_id}/status")
async def get_escrow_status(
    escrow_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Phase 4: On-chain status with balance verification and explorer URL."""
    result = await db.execute(
        select(EscrowContract).where(
            EscrowContract.escrow_id == uuid.UUID(escrow_id),
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Escrow not found")
    contract_ref = row.contract_ref or ""
    agreed_usdc = float(row.amount) if row.amount else 0.0
    on_chain_balance_usdc = 0.0
    sdk_available = False
    try:
        from blockchain.sdk_client import get_algorand_client
        import os
        client = get_algorand_client()
        sdk_available = True
        asset_id = int(os.getenv("ALGORAND_USDC_ASSET_ID", "10458941"))
        info = client.get_account_info(contract_ref)
        for asset in info.get("assets", []):
            if asset["asset-id"] == asset_id:
                on_chain_balance_usdc = asset.get("amount", 0) / 1_000_000.0
                break
    except Exception:
        pass
    balance_verified = abs(on_chain_balance_usdc - agreed_usdc) <= 0.01 if agreed_usdc else False
    network = __import__("os").getenv("ALGORAND_NETWORK", "testnet")
    explorer_url = ""
    if contract_ref and len(contract_ref) == 58 and network == "testnet":
        explorer_url = f"https://lora.algokit.io/testnet/account/{contract_ref}"
    elif contract_ref and len(contract_ref) == 58 and network == "mainnet":
        explorer_url = f"https://lora.algokit.io/testnet/account/{contract_ref}"
    return {
        "escrow_id": escrow_id,
        "contract_ref": contract_ref,
        "status": row.status or "UNKNOWN",
        "on_chain_balance_usdc": on_chain_balance_usdc,
        "agreed_amount_usdc": agreed_usdc,
        "balance_verified": balance_verified,
        "sdk_available": sdk_available,
        "explorer_url": explorer_url,
    }
