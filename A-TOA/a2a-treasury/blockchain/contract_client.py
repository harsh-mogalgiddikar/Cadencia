"""
blockchain/contract_client.py — Python client for TreasuryEscrow smart contract.

Wraps all ABI method calls using algosdk + AtomicTransactionComposer.
Provides high-level methods for deploy, fund, release, refund, dispute, and queries.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("a2a_treasury")

# ─── Environment ────────────────────────────────────────────────────────────────
ALGORAND_ALGOD_ADDRESS = os.getenv(
    "ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"
)
ALGORAND_ALGOD_TOKEN = os.getenv("ALGORAND_ALGOD_TOKEN", "")
ALGORAND_NETWORK = os.getenv("ALGORAND_NETWORK", "testnet")
USDC_ASSET_ID = int(os.getenv("ALGORAND_USDC_ASSET_ID", "10458941"))
PLATFORM_MNEMONIC = os.getenv("ALGORAND_ESCROW_CREATOR_MNEMONIC", "")

# Try imports
try:
    from algosdk import account, mnemonic
    from algosdk.abi import Method
    from algosdk.atomic_transaction_composer import (
        AccountTransactionSigner,
        AtomicTransactionComposer,
        TransactionWithSigner,
    )
    from algosdk.logic import get_application_address
    from algosdk.transaction import (
        ApplicationCreateTxn,
        AssetTransferTxn,
        OnComplete,
        PaymentTxn,
        StateSchema,
        wait_for_confirmation,
    )
    from algosdk.v2client import algod

    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False
    logger.warning("algosdk not installed — TreasuryEscrowClient in simulation mode")


# ─── ABI Method Signatures ─────────────────────────────────────────────────────
ABI_INIT = Method.from_signature(
    "init(address,address,address,byte[],uint64,uint64)void"
) if ALGOSDK_AVAILABLE else None

ABI_OPT_IN_USDC = Method.from_signature(
    "opt_in_to_usdc()void"
) if ALGOSDK_AVAILABLE else None

ABI_FUND = Method.from_signature(
    "fund(axfer,byte[])void"
) if ALGOSDK_AVAILABLE else None

ABI_RELEASE = Method.from_signature(
    "release(byte[])void"
) if ALGOSDK_AVAILABLE else None

ABI_REFUND = Method.from_signature(
    "refund(byte[])void"
) if ALGOSDK_AVAILABLE else None

ABI_DISPUTE = Method.from_signature(
    "dispute()void"
) if ALGOSDK_AVAILABLE else None

ABI_GET_STATUS = Method.from_signature(
    "get_status()uint64"
) if ALGOSDK_AVAILABLE else None

ABI_GET_DETAILS = Method.from_signature(
    "get_details()(byte[],byte[],uint64,uint64)"
) if ALGOSDK_AVAILABLE else None


class TreasuryEscrowClient:
    """
    High-level client for TreasuryEscrow smart contract interactions.

    All methods support simulation mode when ALGORAND_SIMULATION=true or
    when algosdk is not available.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._platform_private_key: str | None = None
        self._platform_address: str | None = None

        if not ALGOSDK_AVAILABLE:
            logger.warning("TreasuryEscrowClient: algosdk not available")
            return

        try:
            self._client = algod.AlgodClient(
                algod_token=ALGORAND_ALGOD_TOKEN or "",
                algod_address=ALGORAND_ALGOD_ADDRESS,
            )
            if PLATFORM_MNEMONIC:
                self._platform_private_key = mnemonic.to_private_key(PLATFORM_MNEMONIC)
                self._platform_address = account.address_from_private_key(
                    self._platform_private_key
                )
            logger.info(
                "TreasuryEscrowClient initialized | platform: %s",
                self._platform_address[:8] + "..." if self._platform_address else "none",
            )
        except Exception as e:
            logger.warning("TreasuryEscrowClient init failed: %s", e)

    @property
    def sdk_available(self) -> bool:
        return (
            ALGOSDK_AVAILABLE
            and self._client is not None
            and self._platform_private_key is not None
        )

    def _get_signer(self, caller_mnemonic: str | None = None) -> tuple[str, str, Any]:
        """
        Returns (private_key, address, AccountTransactionSigner).
        If caller_mnemonic is provided, uses that; otherwise uses platform key.
        """
        if caller_mnemonic:
            pk = mnemonic.to_private_key(caller_mnemonic)
            addr = account.address_from_private_key(pk)
        else:
            pk = self._platform_private_key
            addr = self._platform_address
        if not pk or not addr:
            raise ValueError("No private key available (mnemonic not configured)")
        return pk, addr, AccountTransactionSigner(pk)

    # ─── deploy_new_escrow ──────────────────────────────────────────────────
    async def deploy_new_escrow(
        self,
        buyer_addr: str,
        seller_addr: str,
        platform_addr: str,
        session_id: str,
        agreed_amount: int,
        fx_rate: int,
    ) -> int:
        """
        Deploy a new TreasuryEscrow contract instance.

        Args:
            buyer_addr: Algorand address of the buyer
            seller_addr: Algorand address of the seller
            platform_addr: Algorand address of the platform (arbitrator)
            session_id: Negotiation session ID string
            agreed_amount: USDC amount in micro-units (uint64)
            fx_rate: INR/USDC rate scaled x10^6 (uint64)

        Returns:
            app_id: The deployed application ID
        """
        if not self.sdk_available:
            raise RuntimeError("SDK not available for deployment")

        import asyncio

        pk, addr, signer = self._get_signer()

        def _deploy() -> int:
            # ── Step 1: Read compiled TEAL ──────────────────────────────────
            contracts_dir = Path(__file__).parent / "contracts"
            approval_teal = clear_teal = None

            # Search common output locations
            for teal_dir in [
                contracts_dir / "artifacts" / "TreasuryEscrow",
                contracts_dir / "out",
                contracts_dir,
            ]:
                a = teal_dir / "approval.teal"
                c = teal_dir / "clear.teal"
                if not a.exists():
                    a = teal_dir / "TreasuryEscrow.approval.teal"
                    c = teal_dir / "TreasuryEscrow.clear.teal"
                if a.exists() and c.exists():
                    approval_teal = a.read_text()
                    clear_teal = c.read_text()
                    break

            if not approval_teal or not clear_teal:
                raise FileNotFoundError(
                    "Compiled TEAL not found. Run 'python -m blockchain.contracts.deploy' "
                    "or 'algokit compile py blockchain/contracts/treasury_escrow.py' first."
                )

            # Compile TEAL → bytecode
            approval_compiled = self._client.compile(approval_teal)["result"]
            clear_compiled = self._client.compile(clear_teal)["result"]

            import base64

            approval_program = base64.b64decode(approval_compiled)
            clear_program = base64.b64decode(clear_compiled)

            # ── Step 2: Create application ──────────────────────────────────
            sp = self._client.suggested_params()
            global_schema = StateSchema(num_uints=4, num_byte_slices=5)
            local_schema = StateSchema(num_uints=0, num_byte_slices=0)

            create_txn = ApplicationCreateTxn(
                sender=addr,
                sp=sp,
                on_complete=OnComplete.NoOpOC,
                approval_program=approval_program,
                clear_program=clear_program,
                global_schema=global_schema,
                local_schema=local_schema,
            )
            signed = create_txn.sign(pk)
            tx_id = self._client.send_transaction(signed)
            result = wait_for_confirmation(self._client, tx_id, 10)
            app_id = result["application-index"]
            app_address = get_application_address(app_id)

            logger.info("Contract created | app_id=%d | app_address=%s", app_id, app_address)

            # ── Step 3: Fund contract for MBR (0.3 ALGO) ───────────────────
            sp = self._client.suggested_params()
            fund_txn = PaymentTxn(
                sender=addr,
                sp=sp,
                receiver=app_address,
                amt=300_000,  # 0.3 ALGO
            )
            signed_fund = fund_txn.sign(pk)
            fund_tx = self._client.send_transaction(signed_fund)
            wait_for_confirmation(self._client, fund_tx, 10)

            # ── Step 4: Opt contract into USDC ASA ─────────────────────────
            sp = self._client.suggested_params()
            sp.flat_fee = True
            sp.fee = 2000  # cover inner txn

            atc = AtomicTransactionComposer()
            atc.add_method_call(
                app_id=app_id,
                method=ABI_OPT_IN_USDC,
                sender=addr,
                sp=sp,
                signer=signer,
            )
            atc.execute(self._client, 10)

            # ── Step 5: Init contract with escrow parameters ───────────────
            sp = self._client.suggested_params()
            atc = AtomicTransactionComposer()
            atc.add_method_call(
                app_id=app_id,
                method=ABI_INIT,
                sender=addr,
                sp=sp,
                signer=signer,
                method_args=[
                    buyer_addr,
                    seller_addr,
                    platform_addr,
                    session_id.encode("utf-8"),
                    agreed_amount,
                    fx_rate,
                ],
            )
            atc.execute(self._client, 10)
            logger.info("Contract initialized | session=%s | amount=%d", session_id, agreed_amount)

            return app_id

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _deploy)

    # ─── fund_escrow ────────────────────────────────────────────────────────
    async def fund_escrow(
        self,
        app_id: int,
        buyer_mnemonic: str,
        payment_amount_usdc: int,
    ) -> str:
        """
        Fund the escrow by calling the fund() ABI method with an attached
        USDC AssetTransfer.

        Args:
            app_id: The application ID of the escrow contract
            buyer_mnemonic: 25-word mnemonic of the buyer
            payment_amount_usdc: USDC amount in micro-units

        Returns:
            tx_id: Transaction ID of the fund call
        """
        if not self.sdk_available:
            raise RuntimeError("SDK not available")

        import asyncio

        pk, addr, signer = self._get_signer(buyer_mnemonic)
        app_address = get_application_address(app_id)

        def _fund() -> str:
            sp = self._client.suggested_params()
            sp.flat_fee = True
            sp.fee = 1000

            # USDC transfer to the contract (grouped with app call)
            usdc_txn = AssetTransferTxn(
                sender=addr,
                sp=sp,
                receiver=app_address,
                amt=payment_amount_usdc,
                index=USDC_ASSET_ID,
            )
            tws = TransactionWithSigner(usdc_txn, signer)

            # Read session_id from contract state for verification
            app_info = self._client.application_info(app_id)
            session_id_bytes = b""
            for gs in app_info.get("params", {}).get("global-state", []):
                import base64
                key = base64.b64decode(gs["key"]).decode("utf-8", errors="ignore")
                if key == "session_id":
                    session_id_bytes = base64.b64decode(gs["value"].get("bytes", ""))
                    break

            atc = AtomicTransactionComposer()
            sp_call = self._client.suggested_params()
            sp_call.flat_fee = True
            sp_call.fee = 1000

            atc.add_method_call(
                app_id=app_id,
                method=ABI_FUND,
                sender=addr,
                sp=sp_call,
                signer=signer,
                method_args=[tws, session_id_bytes],
            )
            result = atc.execute(self._client, 10)
            tx_id = result.tx_ids[0]
            logger.info("Escrow funded | app_id=%d | tx_id=%s", app_id, tx_id)
            return tx_id

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fund)

    # ─── release_escrow ─────────────────────────────────────────────────────
    async def release_escrow(
        self,
        app_id: int,
        caller_mnemonic: str,
        merkle_root: bytes,
    ) -> str:
        """
        Release escrowed USDC to the seller.

        Args:
            app_id: The application ID of the escrow contract
            caller_mnemonic: Mnemonic of caller (platform or buyer)
            merkle_root: SHA-256 Merkle root of negotiation audit trail

        Returns:
            tx_id: Transaction ID of the release call
        """
        if not self.sdk_available:
            raise RuntimeError("SDK not available")

        import asyncio

        pk, addr, signer = self._get_signer(caller_mnemonic)

        def _release() -> str:
            sp = self._client.suggested_params()
            sp.flat_fee = True
            sp.fee = 2000  # cover inner USDC transfer

            # Need to include seller's USDC ASA account in foreign accounts/assets
            app_info = self._client.application_info(app_id)
            seller_addr = ""
            for gs in app_info.get("params", {}).get("global-state", []):
                import base64
                key = base64.b64decode(gs["key"]).decode("utf-8", errors="ignore")
                if key == "seller_address":
                    from algosdk.encoding import encode_address
                    raw = base64.b64decode(gs["value"].get("bytes", ""))
                    seller_addr = encode_address(raw)
                    break

            atc = AtomicTransactionComposer()
            atc.add_method_call(
                app_id=app_id,
                method=ABI_RELEASE,
                sender=addr,
                sp=sp,
                signer=signer,
                method_args=[merkle_root],
                foreign_assets=[USDC_ASSET_ID],
                accounts=[seller_addr] if seller_addr else [],
            )
            result = atc.execute(self._client, 10)
            tx_id = result.tx_ids[0]
            logger.info("Escrow released | app_id=%d | tx_id=%s", app_id, tx_id)
            return tx_id

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _release)

    # ─── refund_escrow ──────────────────────────────────────────────────────
    async def refund_escrow(
        self,
        app_id: int,
        platform_mnemonic: str,
        reason: bytes,
    ) -> str:
        """
        Refund escrowed USDC back to the buyer.

        Args:
            app_id: The application ID of the escrow contract
            platform_mnemonic: Platform's 25-word mnemonic
            reason: Reason bytes for the refund

        Returns:
            tx_id: Transaction ID of the refund call
        """
        if not self.sdk_available:
            raise RuntimeError("SDK not available")

        import asyncio

        pk, addr, signer = self._get_signer(platform_mnemonic)

        def _refund() -> str:
            sp = self._client.suggested_params()
            sp.flat_fee = True
            sp.fee = 2000  # cover inner USDC transfer

            # Read buyer address from on-chain state
            app_info = self._client.application_info(app_id)
            buyer_addr = ""
            for gs in app_info.get("params", {}).get("global-state", []):
                import base64
                key = base64.b64decode(gs["key"]).decode("utf-8", errors="ignore")
                if key == "buyer_address":
                    from algosdk.encoding import encode_address
                    raw = base64.b64decode(gs["value"].get("bytes", ""))
                    buyer_addr = encode_address(raw)
                    break

            atc = AtomicTransactionComposer()
            atc.add_method_call(
                app_id=app_id,
                method=ABI_REFUND,
                sender=addr,
                sp=sp,
                signer=signer,
                method_args=[reason],
                foreign_assets=[USDC_ASSET_ID],
                accounts=[buyer_addr] if buyer_addr else [],
            )
            result = atc.execute(self._client, 10)
            tx_id = result.tx_ids[0]
            logger.info("Escrow refunded | app_id=%d | tx_id=%s", app_id, tx_id)
            return tx_id

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _refund)

    # ─── dispute_escrow ─────────────────────────────────────────────────────
    async def dispute_escrow(
        self,
        app_id: int,
        caller_mnemonic: str,
    ) -> str:
        """
        Flag escrow as DISPUTED.

        Args:
            app_id: The application ID of the escrow contract
            caller_mnemonic: Mnemonic of caller (buyer or seller)

        Returns:
            tx_id: Transaction ID of the dispute call
        """
        if not self.sdk_available:
            raise RuntimeError("SDK not available")

        import asyncio

        pk, addr, signer = self._get_signer(caller_mnemonic)

        def _dispute() -> str:
            sp = self._client.suggested_params()

            atc = AtomicTransactionComposer()
            atc.add_method_call(
                app_id=app_id,
                method=ABI_DISPUTE,
                sender=addr,
                sp=sp,
                signer=signer,
            )
            result = atc.execute(self._client, 10)
            tx_id = result.tx_ids[0]
            logger.info("Escrow disputed | app_id=%d | tx_id=%s", app_id, tx_id)
            return tx_id

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _dispute)

    # ─── get_escrow_status ──────────────────────────────────────────────────
    async def get_escrow_status(self, app_id: int) -> dict:
        """
        Query on-chain escrow status and details.

        Returns:
            dict with keys: app_id, status, status_label, session_id,
            merkle_root, agreed_amount_usdc, app_address
        """
        if not self.sdk_available:
            return {
                "app_id": app_id,
                "status": -1,
                "status_label": "SDK_UNAVAILABLE",
                "error": "algosdk not available",
            }

        import asyncio

        def _query() -> dict:
            STATUS_LABELS = {
                0: "PENDING",
                1: "FUNDED",
                2: "RELEASED",
                3: "REFUNDED",
                4: "DISPUTED",
            }

            try:
                app_address = get_application_address(app_id)

                # Use ABI to call get_details
                pk, addr, signer = self._get_signer()
                sp = self._client.suggested_params()

                atc = AtomicTransactionComposer()
                atc.add_method_call(
                    app_id=app_id,
                    method=ABI_GET_DETAILS,
                    sender=addr,
                    sp=sp,
                    signer=signer,
                )
                result = atc.execute(self._client, 10)
                # result.abi_results[0].return_value is tuple
                details = result.abi_results[0].return_value

                session_id_bytes = details[0] if details[0] else b""
                merkle_root_bytes = details[1] if details[1] else b""
                agreed_amount = details[2]
                status_int = details[3]

                return {
                    "app_id": app_id,
                    "app_address": app_address,
                    "status": status_int,
                    "status_label": STATUS_LABELS.get(status_int, "UNKNOWN"),
                    "session_id": session_id_bytes.decode("utf-8", errors="replace")
                    if isinstance(session_id_bytes, bytes)
                    else str(session_id_bytes),
                    "merkle_root": merkle_root_bytes.hex()
                    if isinstance(merkle_root_bytes, bytes)
                    else str(merkle_root_bytes),
                    "agreed_amount_usdc": agreed_amount,
                    "agreed_amount_usdc_display": agreed_amount / 1_000_000
                    if agreed_amount
                    else 0.0,
                }
            except Exception as e:
                logger.error("get_escrow_status failed for app %d: %s", app_id, e)
                return {
                    "app_id": app_id,
                    "status": -1,
                    "status_label": "ERROR",
                    "error": str(e),
                }

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _query)


# Module-level singleton
treasury_escrow_client = TreasuryEscrowClient()
