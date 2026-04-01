"""
AnchorService — anchors session Merkle root on Algorand testnet.
Broadcasts a minimum-fee PaymentTxn with the Merkle root in the note field.
The tx_id proves the audit trail existed at a specific block.
Layer: Verification Layer — Agentic Commerce Framework
"""
from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Negotiation

logger = logging.getLogger("a2a_treasury")


class AnchorService:
    """Anchors session Merkle root on-chain for tamper-proof audit."""

    @staticmethod
    async def anchor_session(
        session_id: str,
        merkle_root: str,
        db: AsyncSession,
    ) -> dict:
        """Anchor a Merkle root on Algorand testnet.

        Modes:
        - ANCHOR_DISABLED:    returns immediately
        - LIVE:               broadcasts real PaymentTxn
        """
        try:
            # Check if anchoring is enabled
            anchor_enabled = os.getenv("ANCHOR_ENABLED", "false").lower() == "true"
            if not anchor_enabled:
                return {"anchored": False, "reason": "ANCHOR_DISABLED"}

            sid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id

            # ── LIVE MODE ──────────────────────────────────────────────
            from algosdk import mnemonic, transaction
            from algosdk.v2client import algod

            buyer_address = os.getenv("BUYER_WALLET_ADDRESS", "")
            buyer_mnemonic_str = os.getenv("BUYER_WALLET_MNEMONIC", "")

            if not buyer_address or not buyer_mnemonic_str:
                return {"anchored": False, "reason": "WALLET_NOT_CONFIGURED"}

            algod_token = os.getenv("ALGORAND_ALGOD_TOKEN", "")
            algod_address = os.getenv(
                "ALGORAND_ALGOD_ADDRESS",
                "https://testnet-api.algonode.cloud",
            )
            algod_client = algod.AlgodClient(algod_token, algod_address)

            private_key = mnemonic.to_private_key(buyer_mnemonic_str)

            sp = algod_client.suggested_params()
            sp.flat_fee = True
            sp.fee = 1000  # 0.001 ALGO min fee

            note_str = f"cadencia:anchor:v1:{session_id}:{merkle_root}"
            note_bytes = note_str.encode()

            # Self-transfer (zero net cost beyond fee)
            txn = transaction.PaymentTxn(
                sender=buyer_address,
                sp=sp,
                receiver=buyer_address,
                amt=0,
                note=note_bytes,
            )
            signed_txn = txn.sign(private_key)

            tx_id = algod_client.send_transaction(signed_txn)

            # Wait for confirmation
            try:
                transaction.wait_for_confirmation(algod_client, tx_id, wait_rounds=10)
            except Exception as conf_err:
                logger.warning(
                    "Anchor tx broadcast OK but confirmation timeout: %s",
                    conf_err,
                )

            # Store tx_id in DB
            neg_result = await db.execute(
                select(Negotiation).where(Negotiation.session_id == sid),
            )
            neg = neg_result.scalar_one_or_none()
            if neg:
                neg.anchor_tx_id = tx_id
                await db.flush()

            explorer_url = (
                f"https://lora.algokit.io/testnet/transaction/{tx_id}"
            )

            logger.info(
                "Anchor LIVE for session %s: %s",
                str(session_id)[:8],
                tx_id,
            )
            return {
                "anchored": True,
                "tx_id": tx_id,
                "simulation": False,
                "network": "algorand-testnet",
                "note": note_str,
                "explorer_url": explorer_url,
            }

        except Exception as e:
            logger.exception(
                "Anchor service error for session %s: %s",
                str(session_id)[:8],
                e,
            )
            return {"anchored": False, "reason": str(e)}
