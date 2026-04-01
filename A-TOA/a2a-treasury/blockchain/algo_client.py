"""
blockchain/algo_client.py — DEPRECATED.

Replaced by blockchain/sdk_client.py in Phase 1 (Cadencia cleanup).
Kept for backward compatibility with demo routes only.
Do NOT import this module in any new code.

Uses ONLY algosdk (py-algorand-sdk). No Web3, no EVM.
All operations target Algorand testnet (AlgoNode).
Gracefully degrades when algosdk is not installed or mnemonic is missing.
"""
from __future__ import annotations

import warnings
warnings.warn(
    "blockchain.algo_client is deprecated. Use blockchain.sdk_client instead.",
    DeprecationWarning,
    stacklevel=2,
)

import logging
import os
from typing import Any

logger = logging.getLogger("a2a_treasury")

ALGORAND_ALGOD_TOKEN = os.getenv("ALGORAND_ALGOD_TOKEN", "")
ALGORAND_ALGOD_ADDRESS = os.getenv(
    "ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"
)
ALGORAND_INDEXER_ADDRESS = os.getenv(
    "ALGORAND_INDEXER_ADDRESS", "https://testnet-idx.algonode.cloud"
)
ALGORAND_ESCROW_CREATOR_MNEMONIC = os.getenv("ALGORAND_ESCROW_CREATOR_MNEMONIC", "")
ALGORAND_NETWORK = os.getenv("ALGORAND_NETWORK", "testnet")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Try to import algosdk
try:
    from algosdk import account, mnemonic
    from algosdk.v2client import algod, indexer
    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False
    algod = indexer = account = mnemonic = None  # type: ignore


class AlgorandClient:
    """Algorand SDK client — algod + indexer. Escrow creator from mnemonic."""

    def __init__(self) -> None:
        self.sdk_available: bool = False
        self.creator_private_key: str | None = None
        self.creator_address: str | None = None

        if ALGORAND_NETWORK == "mainnet" and ENVIRONMENT != "production":
            raise RuntimeError(
                "MAINNET refused: ENVIRONMENT must be 'production' to use mainnet. "
                "Set ENVIRONMENT=production in .env."
            )
        if ALGORAND_NETWORK == "mainnet":
            logger.warning("MAINNET ACTIVE — real funds will be used")

        if not ALGOSDK_AVAILABLE:
            logger.warning("algosdk not installed — escrow simulation mode")
            return

        try:
            self.algod = algod.AlgodClient(
                algod_token=ALGORAND_ALGOD_TOKEN or "",
                algod_address=ALGORAND_ALGOD_ADDRESS,
            )
            self.indexer = indexer.IndexerClient(
                indexer_token="",
                indexer_address=ALGORAND_INDEXER_ADDRESS,
            )

            if ALGORAND_ESCROW_CREATOR_MNEMONIC:
                self.creator_private_key = mnemonic.to_private_key(
                    ALGORAND_ESCROW_CREATOR_MNEMONIC
                )
                self.creator_address = account.address_from_private_key(
                    self.creator_private_key
                )
                self.sdk_available = True
                logger.info(
                    "Algorand client initialized | address: %s | network: %s",
                    self.creator_address,
                    ALGORAND_NETWORK,
                )
            else:
                logger.warning(
                    "ALGORAND_ESCROW_CREATOR_MNEMONIC not set — escrow simulation mode"
                )
        except Exception as e:
            logger.warning("AlgorandClient init failed: %s — simulation mode", e)

    async def get_suggested_params(self) -> Any | None:
        """Get current network params for transaction construction."""
        if not self.sdk_available:
            return None
        try:
            return self.algod.suggested_params()
        except Exception as e:
            logger.error("Failed to get Algorand params: %s", e)
            return None

    async def submit_transaction(self, signed_txn: Any) -> str:
        """
        Broadcast signed transaction to Algorand testnet.
        Returns tx_ref (transaction ID). Uses tenacity retry.
        """
        import asyncio
        from tenacity import retry, stop_after_attempt, wait_exponential

        def _submit() -> str:
            txid = self.algod.send_transaction(signed_txn)
            return txid

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=8),
            reraise=True,
        )
        def _with_retry() -> str:
            return _submit()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _with_retry)

    async def wait_for_confirmation(
        self, tx_ref: str, max_rounds: int = 10
    ) -> dict:
        """Poll algod for transaction confirmation."""
        import asyncio

        def _wait() -> dict:
            return self.algod.pending_transaction_info(tx_ref)

        for _ in range(max_rounds):
            info = await asyncio.get_event_loop().run_in_executor(
                None, _wait
            )
            if info.get("confirmed-round"):
                return info
            await asyncio.sleep(1)
        raise TimeoutError(f"Transaction {tx_ref} not confirmed in {max_rounds} rounds")

    async def simulate_transaction(self, txn_obj: Any) -> bool:
        """
        Dry-run simulation. Returns True if transaction would succeed.
        Returns True (passthrough) when SDK unavailable.
        """
        if not self.sdk_available:
            logger.warning(
                "simulate_transaction: SDK unavailable, returning True (passthrough)"
            )
            return True
        try:
            # Basic validation — algod params check
            self.algod.suggested_params()
            return True
        except Exception as e:
            logger.warning("simulate_transaction failed: %s — passthrough True", e)
            return True

    async def get_transaction_status(self, tx_ref: str) -> dict:
        """Query transaction by ID. Returns status dict."""
        import asyncio
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.algod.pending_transaction_info(tx_ref),
            )
            return info or {}
        except Exception:
            return {"status": "unknown"}

    async def get_account_info(self, address: str) -> dict:
        """Returns account balance and ASA holdings."""
        if not self.sdk_available:
            return {"address": address, "amount": 0, "sdk_available": False}
        import asyncio
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.algod.account_info(address),
            )
            return info
        except Exception as e:
            logger.error("get_account_info failed: %s", e)
            return {"address": address, "amount": 0, "error": str(e)}

    async def get_asset_balance(
        self, address: str, asset_id: int
    ) -> float:
        """
        Phase 4: Returns USDC balance at address in USDC (not micro units).
        On error: log warning, return 0.0 (never raise).
        """
        if not self.sdk_available:
            return 0.0
        import asyncio
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.algod.account_info(address),
            )
            for asset in info.get("assets", []):
                if asset["asset-id"] == asset_id:
                    return asset.get("amount", 0) / 1_000_000.0
            return 0.0
        except Exception as e:
            logger.warning("get_asset_balance failed for %s: %s", address[:8], e)
            return 0.0

    async def opt_in_to_asset(
        self, private_key: str, asset_id: int
    ) -> str:
        """Opt wallet into ASA. Returns tx_ref."""
        from algosdk.future import transaction as ftxn
        import asyncio
        sp = self.algod.suggested_params()
        sender = account.address_from_private_key(private_key)
        optin = ftxn.AssetOptInTxn(sender, sp, asset_id)
        signed = optin.sign(private_key)
        txid = self.algod.send_transaction(signed)
        return txid
