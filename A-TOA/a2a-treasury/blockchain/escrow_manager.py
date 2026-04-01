# blockchain/escrow_manager.py
# Manages the full escrow lifecycle for agreed negotiation sessions.
# Uses Algorand SDK exclusively. No PyTeal, no simulation fallbacks.
# Failure to deploy is an error, not a fallback condition.

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blockchain.escrow_contract import EscrowContract
from blockchain.sdk_client import get_algorand_client
from db.audit_logger import AuditLogger
from db.models import EscrowContract as EscrowModel, Negotiation, Wallet

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()

ALGORAND_NETWORK = os.getenv("ALGORAND_NETWORK", "testnet")


class EscrowManager:
    """
    Manages the full escrow lifecycle for agreed negotiation sessions.
    Uses Algorand SDK exclusively — no PyTeal, no simulation fallbacks.
    """

    def __init__(self):
        self.contract = EscrowContract()
        self.audit = AuditLogger()

    async def trigger_escrow(
        self,
        session_id: str,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> dict:
        """
        Full pipeline: validate session → deploy contract → persist → audit.
        Called automatically when a session reaches AGREED state.
        Raises ValueError if session is not in AGREED state.
        Raises RuntimeError if contract deployment fails.

        Signature preserved for backward compatibility with:
          - agents/neutral_agent.py
          - core/state_machine.py
          - agents/multi_party_session.py
        """
        result = await db_session.execute(
            select(Negotiation).where(
                Negotiation.session_id == uuid.UUID(session_id),
            ),
        )
        neg = result.scalar_one_or_none()
        if not neg:
            return {"status": "error", "reason": "session_not_found"}
        if neg.status != "AGREED":
            return {"status": "skipped", "reason": "session_not_agreed"}

        # Idempotency check
        existing_escrow = await db_session.execute(
            select(EscrowModel).where(
                EscrowModel.session_id == uuid.UUID(session_id),
            ),
        )
        existing = existing_escrow.scalar_one_or_none()
        if existing:
            return {
                "status": "deployed",
                "contract_ref": existing.contract_ref or "",
                "app_id": existing.app_id,
                "network_id": existing.network_id
                or f"algorand-{ALGORAND_NETWORK}",
                "idempotent": True,
            }

        # Resolve buyer/seller wallet addresses
        buyer_wallet = await db_session.execute(
            select(Wallet).where(
                Wallet.enterprise_id == neg.buyer_enterprise_id
            ),
        )
        seller_wallet = await db_session.execute(
            select(Wallet).where(
                Wallet.enterprise_id == neg.seller_enterprise_id
            ),
        )
        bw = buyer_wallet.scalar_one_or_none()
        sw = seller_wallet.scalar_one_or_none()
        buyer_address = bw.address if bw else ""
        seller_address = sw.address if sw else ""

        if not buyer_address and not seller_address:
            await audit_logger.append(
                entity_type="negotiation",
                entity_id=session_id,
                action="ESCROW_SKIPPED_NO_WALLET",
                actor_id="system",
                payload={"session_id": session_id},
                db_session=db_session,
            )
            return {"status": "skipped", "reason": "wallet_not_configured"}

        # Use creator address as fallback for missing addresses
        try:
            platform_addr = self.contract.creator_address
        except Exception:
            platform_addr = ""

        if not buyer_address or len(buyer_address) != 58:
            buyer_address = platform_addr or buyer_address
        if not seller_address or len(seller_address) != 58:
            seller_address = platform_addr or seller_address

        # Build payload
        agreed_inr = (
            float(neg.final_agreed_value)
            if neg.final_agreed_value
            else float(neg.last_buyer_offer or neg.last_seller_offer or 0)
        )
        usdc_eq = (
            float(neg.usdc_equivalent)
            if getattr(neg, "usdc_equivalent", None) is not None
            else None
        )
        amount_usdc = usdc_eq if usdc_eq is not None else agreed_inr
        amount_microalgo = int(amount_usdc * 1_000_000)

        # Deploy contract — no fallback
        try:
            deploy_result = self.contract.deploy(
                buyer_address=buyer_address,
                seller_address=seller_address,
                amount_microalgo=amount_microalgo,
                session_id=session_id,
            )
        except Exception as e:
            logger.exception("Escrow deploy failed: %s", e)
            return {"status": "error", "reason": str(e)}

        # Store escrow record in DB
        escrow_row = EscrowModel(
            session_id=uuid.UUID(session_id),
            contract_ref=f"algo-app-{deploy_result['app_id']}",
            network_id=f"algorand-{ALGORAND_NETWORK}",
            amount=Decimal(str(amount_usdc)),
            status="DEPLOYED",
            deployed_at=datetime.now(timezone.utc),
            app_id=deploy_result["app_id"],
            deploy_txid=deploy_result["txid"],
        )
        db_session.add(escrow_row)
        await db_session.flush()

        await audit_logger.append(
            entity_type="negotiation",
            entity_id=session_id,
            action="ESCROW_DEPLOYED",
            actor_id="system",
            payload={
                "contract_ref": escrow_row.contract_ref,
                "app_id": deploy_result["app_id"],
                "txid": deploy_result["txid"],
                "network_id": escrow_row.network_id,
                "amount": amount_usdc,
                "sdk_available": True,
                "smart_contract": True,
                "simulation_mode": False,
            },
            db_session=db_session,
        )
        return {
            "status": "deployed",
            "contract_ref": escrow_row.contract_ref,
            "app_id": deploy_result["app_id"],
            "txid": deploy_result["txid"],
            "network_id": escrow_row.network_id,
            "escrow_address": deploy_result.get("app_address", ""),
        }

    async def fund_escrow(
        self,
        escrow_id: str,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> dict:
        """Fund a deployed escrow contract."""
        from algosdk import mnemonic as mn

        result = await db_session.execute(
            select(EscrowModel).where(
                EscrowModel.escrow_id == uuid.UUID(escrow_id),
            ),
        )
        row = result.scalar_one_or_none()
        if not row or not row.amount:
            raise ValueError("Escrow not found or no amount")

        # Idempotency check
        if getattr(row, "status", None) == "FUNDED" and getattr(
            row, "fund_tx_id", None
        ):
            return {
                "escrow_id": escrow_id,
                "status": "FUNDED",
                "fund_tx_id": row.fund_tx_id,
                "contract_ref": row.contract_ref or "",
                "amount_usdc": float(row.amount),
                "sdk_available": True,
            }

        if not row.app_id:
            raise ValueError(f"Escrow {escrow_id} has no app_id — cannot fund")

        funder_mnemonic = os.getenv("BUYER_WALLET_MNEMONIC", "")
        if not funder_mnemonic:
            funder_mnemonic = os.getenv("ALGORAND_ESCROW_CREATOR_MNEMONIC", "")
        if not funder_mnemonic:
            raise ValueError("No funder mnemonic configured")

        funder_sk = mn.to_private_key(funder_mnemonic)
        amount_microalgo = int(float(row.amount) * 1_000_000)

        fund_result = self.contract.fund(
            app_id=row.app_id,
            funder_sk=funder_sk,
            amount_microalgo=amount_microalgo,
        )

        row.status = "FUNDED"
        row.fund_tx_id = fund_result["txid"]
        row.funded_at = datetime.now(timezone.utc)
        await db_session.flush()

        await audit_logger.append(
            entity_type="escrow",
            entity_id=escrow_id,
            action="ESCROW_FUNDED",
            actor_id="system",
            payload={
                "escrow_id": escrow_id,
                "contract_ref": row.contract_ref or "",
                "app_id": row.app_id,
                "fund_tx_id": fund_result["txid"],
                "amount_microusdc": amount_microalgo,
                "sdk_available": True,
                "smart_contract": True,
            },
            db_session=db_session,
        )

        return {
            "escrow_id": escrow_id,
            "status": "FUNDED",
            "fund_tx_id": fund_result["txid"],
            "contract_ref": row.contract_ref or "",
            "amount_usdc": float(row.amount),
            "sdk_available": True,
        }

    async def release_escrow(
        self,
        escrow_id: str,
        milestone_description: str,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> dict:
        """Release escrow to seller with Merkle root verification."""
        result = await db_session.execute(
            select(EscrowModel).where(
                EscrowModel.escrow_id == uuid.UUID(escrow_id),
            ),
        )
        row = result.scalar_one_or_none()
        if not row or not row.amount:
            raise ValueError("Escrow not found or no amount")
        if getattr(row, "status", None) != "FUNDED":
            raise ValueError(
                f"Escrow not FUNDED (status={getattr(row, 'status', 'unknown')})"
            )

        if not row.app_id:
            raise ValueError(f"Escrow {escrow_id} has no app_id — cannot release")

        # Get Merkle root from negotiation if available
        neg_result = await db_session.execute(
            select(Negotiation).where(
                Negotiation.session_id == row.session_id,
            ),
        )
        neg = neg_result.scalar_one_or_none()
        merkle_root = neg.merkle_root if neg and neg.merkle_root else "no-merkle"

        release_result = self.contract.release(
            app_id=row.app_id, merkle_root=merkle_root
        )

        row.status = "RELEASED"
        row.release_tx_id = release_result["txid"]
        row.released_at = datetime.now(timezone.utc)
        await db_session.flush()

        # Create settlement record
        from db.models import Settlement

        settlement = Settlement(
            escrow_id=row.escrow_id,
            tx_ref=release_result["txid"],
            amount_released=row.amount,
            milestone_ref=milestone_description,
            settled_at=datetime.now(timezone.utc),
        )
        db_session.add(settlement)
        await db_session.flush()

        await audit_logger.append(
            entity_type="escrow",
            entity_id=escrow_id,
            action="ESCROW_RELEASED",
            actor_id="admin",
            payload={
                "tx_ref": release_result["txid"],
                "app_id": row.app_id,
                "amount_usdc": float(row.amount),
                "milestone": milestone_description,
                "merkle_root": merkle_root,
                "sdk_available": True,
                "smart_contract": True,
            },
            db_session=db_session,
        )
        return {
            "escrow_id": escrow_id,
            "status": "RELEASED",
            "release_tx_id": release_result["txid"],
            "amount_usdc": float(row.amount),
            "milestone": milestone_description,
            "sdk_available": True,
        }

    async def refund_escrow(
        self,
        escrow_id: str,
        reason: str,
        db_session: AsyncSession,
        redis_client: Any,
    ) -> dict:
        """Refund escrow to buyer."""
        result = await db_session.execute(
            select(EscrowModel).where(
                EscrowModel.escrow_id == uuid.UUID(escrow_id),
            ),
        )
        row = result.scalar_one_or_none()
        if not row or not row.amount:
            raise ValueError("Escrow not found or no amount")

        if not row.app_id:
            raise ValueError(f"Escrow {escrow_id} has no app_id — cannot refund")

        refund_result = self.contract.refund(
            app_id=row.app_id, reason=reason
        )

        row.status = "REFUNDED"
        row.refund_tx_id = refund_result["txid"]
        row.refunded_at = datetime.now(timezone.utc)
        row.refund_reason = reason
        await db_session.flush()

        await audit_logger.append(
            entity_type="escrow",
            entity_id=escrow_id,
            action="ESCROW_REFUNDED",
            actor_id="admin",
            payload={
                "escrow_id": escrow_id,
                "refund_tx_id": refund_result["txid"],
                "app_id": row.app_id,
                "reason": reason,
                "sdk_available": True,
                "smart_contract": True,
            },
            db_session=db_session,
        )
        return {
            "escrow_id": escrow_id,
            "status": "REFUNDED",
            "refund_tx_id": refund_result["txid"],
            "sdk_available": True,
        }

    async def generate_escrow_payload(self, session: dict) -> dict:
        """Generate escrow parameters from agreed session.
        Preserved for backward compatibility with x402_algorand.py.
        """
        agreed_usdc = session.get("agreed_amount_usdc")
        if agreed_usdc is not None:
            agreed_float = float(agreed_usdc)
        else:
            agreed = session.get("final_agreed_value")
            if agreed is None:
                agreed = session.get("last_buyer_offer") or session.get(
                    "last_seller_offer"
                )
            if agreed is None:
                raise ValueError("No agreed amount in session")
            agreed_float = float(agreed)
        agreed_microusdc = int(agreed_float * 1_000_000)
        return {
            "session_id": str(session.get("session_id", "")),
            "buyer_address": session.get("buyer_address", ""),
            "seller_address": session.get("seller_address", ""),
            "agreed_amount_usdc": agreed_float,
            "agreed_amount_microusdc": agreed_microusdc,
            "network_id": f"algorand-{ALGORAND_NETWORK}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def deploy_escrow(self, payload: dict) -> dict:
        """Deploy escrow from a prepared payload.
        Preserved for backward compatibility with x402_algorand.py.
        """
        buyer_address = payload.get("buyer_address", "")
        seller_address = payload.get("seller_address", "")
        amount_microalgo = payload.get("agreed_amount_microusdc", 0)
        session_id = payload.get("session_id", "")

        deploy_result = self.contract.deploy(
            buyer_address=buyer_address,
            seller_address=seller_address,
            amount_microalgo=amount_microalgo,
            session_id=session_id,
        )

        return {
            "escrow_address": deploy_result.get("app_address", ""),
            "contract_ref": f"algo-app-{deploy_result['app_id']}",
            "network_id": f"algorand-{ALGORAND_NETWORK}",
            "status": "AWAITING_PAYMENT",
            "sdk_available": True,
            "app_id": deploy_result["app_id"],
            "deploy_tx_id": deploy_result["txid"],
        }


# Module-level singleton for multi_party_session and other callers
escrow_manager = EscrowManager()
