# blockchain/escrow_contract.py
# EscrowContract — manages TreasuryEscrow smart contract lifecycle.
# No PyTeal. Uses pre-compiled TEAL from disk + py-algorand-sdk ARC-4 ABI calls.

from algosdk import transaction, account, mnemonic, encoding
from blockchain.sdk_client import get_algorand_client
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class EscrowContract:
    """
    Manages the TreasuryEscrow smart contract lifecycle via the Algorand SDK.
    All methods interact directly with the pre-compiled TEAL approval program.
    ARC-4 ABI method signatures match the compiled contract.
    """

    # ARC-4 ABI method selectors (4-byte selectors from method signatures)
    METHOD_FUND = b"fund(pay)void"
    METHOD_RELEASE = b"release(string)void"
    METHOD_REFUND = b"refund(string)void"

    def __init__(self):
        self.client = get_algorand_client()
        self._creator_sk: Optional[str] = None
        self._creator_address: Optional[str] = None

    @property
    def creator_sk(self) -> str:
        if self._creator_sk is None:
            m = os.environ["ALGORAND_ESCROW_CREATOR_MNEMONIC"]
            self._creator_sk = mnemonic.to_private_key(m)
        return self._creator_sk

    @property
    def creator_address(self) -> str:
        if self._creator_address is None:
            self._creator_address = account.address_from_private_key(self.creator_sk)
        return self._creator_address

    def deploy(
        self,
        buyer_address: str,
        seller_address: str,
        amount_microalgo: int,
        session_id: str,
    ) -> dict:
        """
        Deploy a new escrow application instance.
        Returns: {app_id, app_address, txid}
        Raises on failure — no fallback.
        """
        sp = self.client.get_suggested_params()
        approval_compiled = self.client.compile_teal(self.client.approval_teal)
        clear_compiled = self.client.compile_teal(self.client.clear_teal)

        global_schema = transaction.StateSchema(num_uints=3, num_byte_slices=3)
        local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

        app_args = [
            encoding.decode_address(buyer_address),
            encoding.decode_address(seller_address),
            amount_microalgo.to_bytes(8, "big"),
            session_id.encode("utf-8"),
        ]

        txn = transaction.ApplicationCreateTxn(
            sender=self.creator_address,
            sp=sp,
            on_complete=transaction.OnComplete.NoOpOC,
            approval_program=approval_compiled,
            clear_program=clear_compiled,
            global_schema=global_schema,
            local_schema=local_schema,
            app_args=app_args,
        )

        signed = txn.sign(self.creator_sk)
        result = self.client.submit_and_wait(signed)

        txid = result["txid"]
        app_id = self.client.algod.pending_transaction_info(txid)["application-index"]
        app_address = encoding.encode_address(
            encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
        )

        logger.info("Escrow deployed app_id=%d session=%s", app_id, session_id)
        return {"app_id": app_id, "app_address": app_address, "txid": txid}

    def fund(self, app_id: int, funder_sk: str, amount_microalgo: int) -> dict:
        """
        Fund the escrow. Atomic group: PaymentTxn to app_address + AppCallTxn(fund).
        """
        sp = self.client.get_suggested_params()
        funder_address = account.address_from_private_key(funder_sk)
        app_address = encoding.encode_address(
            encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
        )

        pay_txn = transaction.PaymentTxn(
            sender=funder_address, sp=sp, receiver=app_address, amt=amount_microalgo
        )
        app_txn = transaction.ApplicationCallTxn(
            sender=funder_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"fund"],
        )

        gid = transaction.calculate_group_id([pay_txn, app_txn])
        pay_txn.group = gid
        app_txn.group = gid

        signed_pay = pay_txn.sign(funder_sk)
        signed_app = app_txn.sign(funder_sk)

        result = self.client.submit_group_and_wait([signed_pay, signed_app])
        logger.info("Escrow funded app_id=%d amount=%d", app_id, amount_microalgo)
        return result

    def release(self, app_id: int, merkle_root: str) -> dict:
        """
        Release escrow funds to seller. Includes Merkle root for audit trail.
        """
        sp = self.client.get_suggested_params()
        txn = transaction.ApplicationCallTxn(
            sender=self.creator_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"release", merkle_root.encode("utf-8")],
        )
        signed = txn.sign(self.creator_sk)
        result = self.client.submit_and_wait(signed)
        logger.info("Escrow released app_id=%d", app_id)
        return result

    def refund(self, app_id: int, reason: str) -> dict:
        """
        Refund escrow funds to buyer.
        """
        sp = self.client.get_suggested_params()
        txn = transaction.ApplicationCallTxn(
            sender=self.creator_address,
            sp=sp,
            index=app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"refund", reason.encode("utf-8")],
        )
        signed = txn.sign(self.creator_sk)
        result = self.client.submit_and_wait(signed)
        logger.info("Escrow refunded app_id=%d reason=%s", app_id, reason)
        return result

    def delete(self, app_id: int) -> dict:
        """
        Delete escrow application — cleanup after settlement.
        """
        sp = self.client.get_suggested_params()
        txn = transaction.ApplicationDeleteTxn(
            sender=self.creator_address, sp=sp, index=app_id
        )
        signed = txn.sign(self.creator_sk)
        return self.client.submit_and_wait(signed)
