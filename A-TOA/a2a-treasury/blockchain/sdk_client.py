# blockchain/sdk_client.py
# Single entry point for all Algorand interactions.
# No PyTeal. Uses pre-compiled TEAL + py-algorand-sdk only.

from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from algosdk import transaction, account, mnemonic, encoding
from pathlib import Path
from typing import Optional
import base64
import os
import logging

logger = logging.getLogger(__name__)

TEAL_DIR = Path(__file__).parent / "contracts" / "teal"


class AlgorandSDKClient:
    """
    Clean Algorand SDK wrapper. Single source of truth for all on-chain operations.
    No simulation fallbacks in this class — callers handle simulation via env flags.
    """

    def __init__(self):
        self.algod_address = os.getenv("ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud")
        self.algod_token = os.getenv("ALGORAND_ALGOD_TOKEN", "")
        self.indexer_address = os.getenv("ALGORAND_INDEXER_ADDRESS", "https://testnet-idx.algonode.cloud")
        self.network = os.getenv("ALGORAND_NETWORK", "testnet")
        self.algod = AlgodClient(self.algod_token, self.algod_address)
        self.indexer = IndexerClient("", self.indexer_address)
        self._approval_teal: Optional[str] = None
        self._clear_teal: Optional[str] = None

    @property
    def approval_teal(self) -> str:
        if self._approval_teal is None:
            self._approval_teal = (TEAL_DIR / "escrow_approval.teal").read_text()
        return self._approval_teal

    @property
    def clear_teal(self) -> str:
        if self._clear_teal is None:
            self._clear_teal = (TEAL_DIR / "escrow_clear.teal").read_text()
        return self._clear_teal

    def get_suggested_params(self) -> transaction.SuggestedParams:
        return self.algod.suggested_params()

    def compile_teal(self, source: str) -> bytes:
        result = self.algod.compile(source)
        return base64.b64decode(result["result"])

    def submit_and_wait(
        self,
        signed_txn: transaction.SignedTransaction,
        wait_rounds: int = 4,
    ) -> dict:
        txid = self.algod.send_transaction(signed_txn)
        result = transaction.wait_for_confirmation(self.algod, txid, wait_rounds)
        return {"txid": txid, "confirmed_round": result["confirmed-round"]}

    def submit_group_and_wait(
        self,
        signed_txns: list,
        wait_rounds: int = 4,
    ) -> dict:
        txid = self.algod.send_transactions(signed_txns)
        result = transaction.wait_for_confirmation(self.algod, txid, wait_rounds)
        return {"txid": txid, "confirmed_round": result["confirmed-round"]}

    def get_account_info(self, address: str) -> dict:
        return self.algod.account_info(address)

    def get_application_info(self, app_id: int) -> dict:
        return self.algod.application_info(app_id)

    def dry_run(self, signed_txn: transaction.SignedTransaction) -> dict:
        dr_request = transaction.create_dryrun(self.algod, [signed_txn])
        return self.algod.dryrun(dr_request)

    def health_check(self) -> dict:
        try:
            status = self.algod.status()
            return {
                "healthy": True,
                "network": self.network,
                "last_round": status["last-round"],
                "catchup_time": status.get("catchup-time", 0),
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}


# Singleton
_client: Optional[AlgorandSDKClient] = None


def get_algorand_client() -> AlgorandSDKClient:
    global _client
    if _client is None:
        _client = AlgorandSDKClient()
    return _client
