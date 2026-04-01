"""
blockchain/payment_handler.py — USDC ASA transfer on Algorand.

Uses algosdk only via the centralized sdk_client.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from blockchain.sdk_client import get_algorand_client
from db.audit_logger import AuditLogger

logger = logging.getLogger("a2a_treasury")
audit_logger = AuditLogger()

ALGORAND_USDC_ASSET_ID = int(os.getenv("ALGORAND_USDC_ASSET_ID", "10458941"))


class PaymentHandler:
    """USDC ASA transfers on Algorand testnet."""

    def __init__(self):
        self._sdk = get_algorand_client()

    async def execute_usdc_transfer(
        self,
        sender_private_key: str,
        receiver_address: str,
        amount_microusdc: int,
        asset_id: int,
        note: str = "",
    ) -> str:
        """Execute USDC ASA transfer. Returns tx_id."""
        from algosdk import transaction, account

        sp = self._sdk.get_suggested_params()
        sender = account.address_from_private_key(sender_private_key)
        txn = transaction.AssetTransferTxn(
            sender=sender,
            sp=sp,
            receiver=receiver_address,
            amt=amount_microusdc,
            index=asset_id,
            note=note.encode() if note else None,
        )
        signed = txn.sign(sender_private_key)
        result = self._sdk.submit_and_wait(signed)
        return result["txid"]

    async def get_usdc_balance(self, address: str) -> float:
        """USDC balance in human-readable units (divide by 1e6)."""
        try:
            info = self._sdk.get_account_info(address)
            for asset in info.get("assets", []):
                if asset["asset-id"] == ALGORAND_USDC_ASSET_ID:
                    return asset.get("amount", 0) / 1_000_000.0
            return 0.0
        except Exception:
            return 0.0

    async def update_wallet_balance(
        self,
        enterprise_id: str,
        new_balance_usdc: float,
        db_session: Any,
    ) -> None:
        """Update wallets.usdc_balance in PostgreSQL."""
        from sqlalchemy import update
        from db.models import Wallet
        import uuid

        await db_session.execute(
            update(Wallet)
            .where(Wallet.enterprise_id == uuid.UUID(enterprise_id))
            .values(usdc_balance=new_balance_usdc),
        )
        await db_session.flush()

    MAX_CONFIRMATION_ROUNDS = 10

    async def wait_for_confirmation(self, tx_id: str) -> dict:
        """Wait up to MAX_CONFIRMATION_ROUNDS for tx confirmation."""
        for attempt in range(self.MAX_CONFIRMATION_ROUNDS):
            try:
                result = self._sdk.algod.pending_transaction_info(tx_id)
                if result and result.get("confirmed-round"):
                    return result
            except Exception:
                pass
            await asyncio.sleep(2)
        raise TimeoutError(
            f"Transaction {tx_id} not confirmed after "
            f"{self.MAX_CONFIRMATION_ROUNDS} rounds"
        )
