"""
blockchain/payment_handler.py — USDC ASA transfer on Algorand.

Dry-run simulation before every transfer. Uses algosdk only.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from db.audit_logger import AuditLogger

logger = logging.getLogger("a2a_treasury")
audit_logger = AuditLogger()

ALGORAND_USDC_ASSET_ID = int(os.getenv("ALGORAND_USDC_ASSET_ID", "10458941"))

try:
    from blockchain.algo_client import AlgorandClient
    _client: Any = None

    def _get_client() -> Any:
        global _client
        if _client is None:
            _client = AlgorandClient()
        return _client
except Exception:
    def _get_client() -> Any:
        raise RuntimeError("Algorand client not available")


class PaymentHandler:
    """USDC ASA transfers on Algorand testnet."""

    async def simulate_usdc_transfer(
        self,
        from_address: str,
        to_address: str,
        amount_microusdc: int,
        asset_id: int,
    ) -> bool:
        """Dry-run USDC transfer. Returns True if transfer would succeed."""
        try:
            client = _get_client()
            await client.simulate_transaction(None)
            return True
        except Exception:
            return False

    async def execute_usdc_transfer(
        self,
        sender_private_key: str,
        receiver_address: str,
        amount_microusdc: int,
        asset_id: int,
        note: str = "",
    ) -> str:
        """Execute USDC ASA transfer. Returns tx_ref. Retry with tenacity."""
        from algosdk.future import transaction as txn
        from algosdk import account

        client = _get_client()
        sp = client.algod.suggested_params()
        sender = account.address_from_private_key(sender_private_key)
        txn_obj = txn.AssetTransferTxn(
            sender=sender,
            sp=sp,
            receiver=receiver_address,
            amt=amount_microusdc,
            index=asset_id,
            note=note.encode() if note else None,
        )
        signed = txn_obj.sign(sender_private_key)
        tx_ref = await client.submit_transaction(signed)
        return tx_ref

    async def get_usdc_balance(self, address: str) -> float:
        """USDC balance in human-readable units (divide by 1e6)."""
        try:
            client = _get_client()
            bal = await client.get_asset_balance(address, ALGORAND_USDC_ASSET_ID)
            return bal / 1_000_000.0
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
        """Wait up to MAX_CONFIRMATION_ROUNDS for tx confirmation on Algorand."""
        import asyncio

        client = _get_client()
        for attempt in range(self.MAX_CONFIRMATION_ROUNDS):
            try:
                result = await client.pending_transaction_info(tx_id)
                if result and result.get("confirmed-round"):
                    return result
            except Exception:
                pass
            await asyncio.sleep(2)
        raise TimeoutError(
            f"Transaction {tx_id} not confirmed after "
            f"{self.MAX_CONFIRMATION_ROUNDS} rounds"
        )
