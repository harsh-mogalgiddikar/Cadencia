"""
core/x402_handler.py — x402 HTTP Payment Protocol on Algorand.

Implements x402 semantics with Algorand native payment transactions:
  - build_402_response()           — seller side (402 body)
  - sign_payment_algorand()        — buyer agent side (sign tx)
  - verify_and_submit_payment()    — server middleware (verify + broadcast)

Production mode requires funded wallets. No SIM- fallback in production path.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("a2a_treasury")

# Algorand testnet explorer (Lora / AlgoKit official)
EXPLORER_BASE = "https://lora.algokit.io/testnet"

from algosdk import account, mnemonic, transaction, encoding
from algosdk.v2client import algod


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

        self.algod_client: Optional[algod.AlgodClient] = None

        try:
            self.algod_client = algod.AlgodClient(
                self.algod_token, self.algod_address
            )
            status = self.algod_client.status()
            logger.info(
                "x402 Algod connected | network=%s | round=%s",
                self.network, status.get("last-round", "?"),
            )
        except Exception as e:
            logger.warning("x402 Algod connection failed: %s", e)
            self.algod_client = None

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
        """
        full_micro_usdc = int(amount_usdc * 1_000_000)
        return {
            "x402Version": 1,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": self.network,
                    "maxAmountRequired": str(full_micro_usdc),
                    "asset": "ALGO-NATIVE",
                    "payTo": escrow_address,
                    "extra": {
                        "session_id": session_id,
                        "inr_amount": inr_amount,
                        "fx_rate": fx_rate,
                        "full_usdc_equivalent": amount_usdc,
                        "full_micro": full_micro_usdc,
                        "description": (
                            "Cadencia Commerce Network — "
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
        Returns base64-encoded signed transaction.
        Raises ValueError if wallet is not configured.
        """
        accepts = payment_requirements.get("accepts", [{}])[0]
        session_id = accepts.get("extra", {}).get("session_id", "unknown")

        mn = buyer_mnemonic or self.buyer_mnemonic
        addr = buyer_address or self.buyer_address

        if not mn or not addr:
            raise ValueError("Buyer wallet mnemonic/address not configured for x402 signing")

        if not self.algod_client:
            raise ValueError("Algod client not available for x402 signing")

        private_key = mnemonic.to_private_key(mn)
        pay_to = accepts["payTo"]
        amount_micro = int(accepts["maxAmountRequired"])

        params = self.algod_client.suggested_params()
        params.flat_fee = True
        params.fee = 1000  # 0.001 ALGO min fee

        nonce = f"{int(time.time())}-{os.urandom(4).hex()}"
        note = f"x402:cadencia:session:{session_id}:{nonce}".encode()

        txn = transaction.PaymentTxn(
            sender=addr,
            sp=params,
            receiver=pay_to,
            amt=amount_micro,
            note=note,
        )
        signed_txn = txn.sign(private_key)
        encoded = encoding.msgpack_encode(signed_txn)

        logger.info(
            "x402 payment signed | session=%s | sender=%s | receiver=%s | amt=%d",
            session_id[:8], addr[:12], pay_to[:12], amount_micro,
        )
        return encoded

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
        Signs and submits a fresh payment transaction.
        No SIM- tokens accepted in production.
        """
        if not self.algod_client:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ALGOD_UNAVAILABLE",
                    "reason": "Algorand node is not connected",
                },
            )

        # Reject SIM- tokens in production
        if x_payment_header.startswith("SIM-"):
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "SIMULATION_NOT_ACCEPTED",
                    "reason": "SIM- tokens are not accepted in production mode",
                },
            )

        try:
            x_payment_header = x_payment_header.strip()
            logger.info("x402 received token length: %s", len(x_payment_header))

            mn = self.buyer_mnemonic
            addr = self.buyer_address
            if not mn or not addr:
                raise ValueError("Buyer wallet mnemonic/address not configured")

            private_key = mnemonic.to_private_key(mn)
            params = self.algod_client.suggested_params()
            params.flat_fee = True
            params.fee = 1000

            nonce = f"{int(time.time())}-{os.urandom(4).hex()}"
            note = f"x402:cadencia:pay:{session_id}:{nonce}".encode()

            pay_to = expected_pay_to or self.seller_address
            amt = expected_amount_micro

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
                "x402 tx broadcast | session=%s | tx_id=%s | amt=%d",
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
                    "x402 tx confirmed | tx_id=%s | round=%s",
                    tx_id, confirmed_round,
                )
            except Exception as conf_err:
                logger.warning(
                    "x402 tx broadcast OK but confirmation timeout: %s",
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

        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error("x402 payment failed: %s", error_msg)

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
        if not tx_id:
            return ""
        return f"{EXPLORER_BASE}/transaction/{tx_id}"

    def get_account_url(self, address: str) -> str:
        """Get the Lora explorer URL for an account."""
        if not address or len(address) != 58:
            return ""
        return f"{EXPLORER_BASE}/account/{address}"


# Singleton
x402_handler = X402Handler()
