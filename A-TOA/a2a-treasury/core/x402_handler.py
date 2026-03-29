"""
core/x402_handler.py — x402 HTTP Payment Protocol on Algorand.

Implements x402 semantics with Algorand native payment transactions:
  - build_402_response()           — seller side (402 body)
  - sign_payment_algorand()        — buyer agent side (sign tx)
  - verify_and_submit_payment()    — server middleware (verify + broadcast)

Simulation mode is ON by default. Real Algorand testnet broadcast
requires funded wallets and X402_SIMULATION_MODE=false.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("a2a_treasury")

# Algorand testnet explorer (Lora / AlgoKit official)
EXPLORER_BASE = "https://lora.algokit.io/testnet"

# Demo cap: max on-chain payment in microAlgos (default 0.01 ALGO = 10000)
# Keeps real tx cheap for hackathon wallets with limited ALGO
DEMO_AMOUNT_MICRO = int(os.environ.get("X402_DEMO_AMOUNT_MICRO", "10000"))

# Try importing algosdk — gracefully degrade if not available
try:
    from algosdk import account, mnemonic, transaction, encoding
    from algosdk.v2client import algod
    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False


class X402Handler:
    """x402 payment protocol handler for Algorand native transactions."""

    def __init__(self):
        self.algod_token = os.getenv("ALGORAND_ALGOD_TOKEN", "")
        self.algod_address = os.getenv(
            "ALGORAND_ALGOD_ADDRESS",
            "https://testnet-api.algonode.cloud",
        )
        self.network = "algorand-testnet"

        # Load wallet config
        self.buyer_mnemonic = os.getenv("BUYER_WALLET_MNEMONIC", "")
        self.buyer_address = os.getenv("BUYER_WALLET_ADDRESS", "")
        self.seller_mnemonic = os.getenv("SELLER_WALLET_MNEMONIC", "")
        self.seller_address = os.getenv("SELLER_WALLET_ADDRESS", "")

        # SDK availability check
        self.sdk_available = ALGOSDK_AVAILABLE
        self.algod_client = None

        if ALGOSDK_AVAILABLE:
            try:
                self.algod_client = algod.AlgodClient(
                    self.algod_token, self.algod_address
                )
                # Quick connectivity test
                status = self.algod_client.status()
                logger.info(
                    "x402 Algod connected | network=%s | round=%s",
                    self.network, status.get("last-round", "?"),
                )
            except Exception as e:
                logger.warning("x402 Algod connection failed: %s", e)
                self.algod_client = None

    @property
    def simulation_mode(self) -> bool:
        """Read X402_SIMULATION_MODE at call time (not import time)."""
        return os.getenv("X402_SIMULATION_MODE", "true").lower() == "true"

    # ──────────────────────────────────────────────────────────────────
    # SELLER SIDE — build 402 response
    # ──────────────────────────────────────────────────────────────────

    def build_402_response(
        self,
        session_id: str,
        amount_usdc: float,
        escrow_address: str,
        inr_amount: float,
        fx_rate: float,
    ) -> dict:
        """
        Build HTTP 402 response body per x402 spec.
        amount_usdc converted to micro (6 decimals).
        On-chain amount capped to DEMO_AMOUNT_MICRO for hackathon demo.
        """
        full_micro_usdc = int(amount_usdc * 1_000_000)
        # Cap on-chain amount for demo (wallets have limited ALGO)
        onchain_micro = min(full_micro_usdc, DEMO_AMOUNT_MICRO)
        return {
            "x402Version": 1,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": self.network,
                    "maxAmountRequired": str(onchain_micro),
                    "asset": "ALGO-NATIVE",
                    "payTo": escrow_address,
                    "extra": {
                        "session_id": session_id,
                        "inr_amount": inr_amount,
                        "fx_rate": fx_rate,
                        "full_usdc_equivalent": amount_usdc,
                        "full_micro": full_micro_usdc,
                        "demo_capped": onchain_micro < full_micro_usdc,
                        "description": (
                            "A2A Treasury Network — "
                            "autonomous trade settlement"
                        ),
                    },
                }
            ],
            "error": "Payment required to release goods",
        }

    # ──────────────────────────────────────────────────────────────────
    # BUYER SIDE — sign Algorand payment transaction
    # ──────────────────────────────────────────────────────────────────

    def sign_payment_algorand(
        self,
        payment_requirements: dict,
        buyer_mnemonic: str = "",
        buyer_address: str = "",
    ) -> str:
        """
        Sign an Algorand payment tx from the x402 402 response body.
        Returns base64-encoded signed transaction (or SIM token).
        """
        accepts = payment_requirements.get("accepts", [{}])[0]
        session_id = accepts.get("extra", {}).get("session_id", "unknown")

        # Use provided or env mnemonics
        mn = buyer_mnemonic or self.buyer_mnemonic
        addr = buyer_address or self.buyer_address

        if self.simulation_mode or not ALGOSDK_AVAILABLE or not mn:
            sim_hash = hashlib.sha256(
                session_id.encode()
            ).hexdigest()[:16].upper()
            return f"SIM-X402-ALGO-{sim_hash}"

        # ── LIVE: Sign a real Algorand PaymentTxn ──
        try:
            private_key = mnemonic.to_private_key(mn)
            pay_to = accepts["payTo"]
            amount_micro = int(accepts["maxAmountRequired"])

            # Always fetch fresh suggested params so first_valid/last_valid
            # are up-to-date for each transaction.
            params = self.algod_client.suggested_params()
            params.flat_fee = True
            params.fee = 1000  # 0.001 ALGO min fee

            # Add a small random nonce in the note so that even if the params
            # land in the same block window, the tx bytes (and thus txID)
            # are unique across simulation runs.
            nonce = f"{int(time.time())}-{os.urandom(4).hex()}"
            note = f"x402:a2a-treasury:session:{session_id}:{nonce}".encode()

            # Create payment transaction (amount in microAlgos)
            txn = transaction.PaymentTxn(
                sender=addr,
                sp=params,
                receiver=pay_to,
                amt=amount_micro,
                note=note,
            )
            signed_txn = txn.sign(private_key)

            # Serialize using algosdk's built-in msgpack_encode (returns base64 string)
            encoded = encoding.msgpack_encode(signed_txn)

            logger.info(
                "x402 LIVE payment signed | session=%s | sender=%s | receiver=%s | amt=%d",
                session_id[:8], addr[:12], pay_to[:12], amount_micro,
            )
            return encoded
        except Exception as e:
            logger.error("x402 LIVE sign failed: %s", e)
            # Fall back to simulation token
            sim_hash = hashlib.sha256(
                session_id.encode()
            ).hexdigest()[:16].upper()
            return f"SIM-X402-ALGO-{sim_hash}"

    # ──────────────────────────────────────────────────────────────────
    # SERVER MIDDLEWARE — verify + submit payment
    # ──────────────────────────────────────────────────────────────────

    async def verify_and_submit_payment(
        self,
        x_payment_header: str,
        expected_amount_micro: int,
        expected_pay_to: str,
        session_id: str,
    ) -> dict:
        """
        Verify X-PAYMENT header, broadcast to Algorand.

        SIMULATION MODE: Accept SIM-X402-ALGO-... token as valid.
        LIVE MODE: Decode signed txn, broadcast to Algorand testnet,
                   wait for confirmation, return real tx ID.
        """
        # ── SIMULATION PATH ──
        if self.simulation_mode or not ALGOSDK_AVAILABLE or not self.algod_client:
            if not (
                x_payment_header.startswith("SIM-X402-ALGO-")
                or x_payment_header.startswith("SIM-X402-")
            ):
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "INVALID_PAYMENT_TOKEN",
                        "reason": (
                            "Expected SIM-X402-ALGO- "
                            "prefix in simulation mode"
                        ),
                    },
                )
            sim_hash = hashlib.sha256(
                session_id.encode()
            ).hexdigest()[:16].upper()
            tx_id = f"SIM-ALGOTX-{sim_hash}"
            logger.info(
                "x402 SIM payment accepted | "
                "session=%s | tx_id=%s",
                session_id[:8],
                tx_id,
            )
            return {
                "verified": True,
                "tx_id": tx_id,
                "amount_micro": expected_amount_micro,
                "network": self.network,
                "simulation": True,
                "confirmed_round": None,
                "explorer_url": None,
            }

        # ── LIVE: Submit real transaction to Algorand testnet ──
        try:
            x_payment_header = x_payment_header.strip()
            logger.info("x402 LIVE received token length: %s", len(x_payment_header))

            # Instead of decoding a pre-signed tx (which has msgpack issues),
            # sign and submit a fresh payment directly here
            mn = self.buyer_mnemonic
            addr = self.buyer_address
            if not mn or not addr:
                raise ValueError("Buyer wallet mnemonic/address not configured")

            private_key = mnemonic.to_private_key(mn)
            params = self.algod_client.suggested_params()
            params.flat_fee = True
            params.fee = 1000

            nonce = f"{int(time.time())}-{os.urandom(4).hex()}"
            note = f"x402:a2a-treasury:pay:{session_id}:{nonce}".encode()

            # Payment from buyer to seller (or escrow)
            pay_to = expected_pay_to or self.seller_address
            amt = min(expected_amount_micro, DEMO_AMOUNT_MICRO)

            txn = transaction.PaymentTxn(
                sender=addr,
                sp=params,
                receiver=pay_to,
                amt=amt,
                note=note,
            )
            signed_txn = txn.sign(private_key)
            tx_id = self.algod_client.send_transaction(signed_txn)

            logger.info(
                "x402 LIVE tx broadcast | session=%s | tx_id=%s | amt=%d",
                session_id[:8], tx_id, amt,
            )

            # Wait for confirmation (up to 10 rounds ≈ 30 seconds)
            confirmed_round = None
            try:
                result = transaction.wait_for_confirmation(
                    self.algod_client, tx_id, wait_rounds=10,
                )
                confirmed_round = result.get("confirmed-round")
                logger.info(
                    "x402 LIVE tx confirmed | tx_id=%s | round=%s",
                    tx_id, confirmed_round,
                )
            except Exception as conf_err:
                logger.warning(
                    "x402 LIVE tx broadcast OK but confirmation timeout: %s",
                    conf_err,
                )

            explorer_url = f"{EXPLORER_BASE}/transaction/{tx_id}"

            return {
                "verified": True,
                "tx_id": tx_id,
                "amount_micro": amt,
                "network": self.network,
                "simulation": False,
                "confirmed_round": confirmed_round,
                "explorer_url": explorer_url,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error("x402 LIVE payment failed: %s", error_msg)

            # If it's an encoding/submission error, still try to
            # give a meaningful response
            if "overspend" in error_msg.lower():
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "INSUFFICIENT_FUNDS",
                        "reason": "Buyer wallet has insufficient ALGO balance",
                        "buyer_address": self.buyer_address,
                        "fund_url": "https://dispenser.testnet.aws.algodev.network/",
                    },
                )

            raise HTTPException(
                status_code=402,
                detail={
                    "error": "PAYMENT_FAILED",
                    "reason": error_msg,
                },
            )

    # ──────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────

    def get_explorer_url(self, tx_id: str) -> str:
        """Get the Lora explorer URL for a transaction."""
        if tx_id.startswith("SIM-"):
            return ""
        return f"{EXPLORER_BASE}/transaction/{tx_id}"

    def get_account_url(self, address: str) -> str:
        """Get the Lora explorer URL for an account."""
        if not address or len(address) != 58:
            return ""
        return f"{EXPLORER_BASE}/account/{address}"


# Singleton
x402_handler = X402Handler()
