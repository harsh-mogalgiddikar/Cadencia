"""framework/settlement/x402_algorand.py

Agentic Commerce Framework (ACF) — x402 + Algorand settlement wrapper.

Wraps the existing x402_handler and EscrowManager behind the generic
SettlementProvider interface without changing underlying payment logic.
"""

from __future__ import annotations

from typing import Dict, List

from blockchain.escrow_manager import escrow_manager
from core.x402_handler import x402_handler
from framework.interfaces import (
    SettlementCapabilities,
    SettlementProvider,
)


class X402AlgorandSettlement(SettlementProvider):
    """Concrete SettlementProvider for x402 payments on Algorand testnet."""

    def get_provider_id(self) -> str:
        return "x402-algorand-testnet"

    def get_supported_networks(self) -> List[str]:
        return ["algorand-testnet"]

    def get_supported_payment_methods(self) -> List[str]:
        return ["x402"]

    def request_payment(
        self,
        session_id: str,
        amount: float,
        currency: str,
        buyer_address: str,
        seller_address: str,
        metadata: Dict,
    ) -> Dict:
        """
        Build an x402 402-response style payment requirement.

        Delegates to core.x402_handler.build_402_response and wraps the result
        in a standardized envelope.
        """
        inr_amount = metadata.get("inr_amount", 0.0)
        fx_rate = metadata.get("fx_rate", 0.0)
        escrow_address = metadata.get("escrow_address", seller_address or buyer_address or "")

        challenge = x402_handler.build_402_response(
            session_id=session_id,
            amount_usdc=amount,
            escrow_address=escrow_address,
            inr_amount=inr_amount,
            fx_rate=fx_rate,
        )

        return {
            "payment_required": True,
            "challenge": challenge,
            "provider": self.get_provider_id(),
            "network": self.get_supported_networks()[0],
            "amount": amount,
        }

    async def verify_payment(
        self,
        session_id: str,
        payment_token: str,
        expected_amount: float,
        expected_pay_to: str | None = None,
    ) -> Dict:
        """
        Verify and submit a signed payment token via x402_handler.
        """
        expected_amount_micro = int(expected_amount * 1_000_000)
        pay_to = expected_pay_to or ""
        result = await x402_handler.verify_and_submit_payment(
            x_payment_header=payment_token,
            expected_amount_micro=expected_amount_micro,
            expected_pay_to=pay_to,
            session_id=session_id,
        )

        return {
            "verified": bool(result.get("verified")),
            "tx_id": result.get("tx_id"),
            "network": result.get("network"),
            "amount_settled": expected_amount,
            "idempotent": False,
            "simulation": False,
            "confirmed_round": result.get("confirmed_round"),
        }

    async def deploy_escrow(
        self,
        session_id: str,
        buyer_address: str,
        seller_address: str,
        amount: float,
    ) -> Dict:
        """
        Deploy an escrow contract for the session via EscrowManager.
        """
        session_dict = {
            "session_id": session_id,
            "buyer_address": buyer_address,
            "seller_address": seller_address,
            "agreed_amount_usdc": amount,
            "current_round": 1,
        }
        payload = await escrow_manager.generate_escrow_payload(session_dict)
        payload["buyer_address"] = buyer_address
        payload["seller_address"] = seller_address

        deploy_result = await escrow_manager.deploy_escrow(payload)

        return {
            "escrow_address": deploy_result.get("escrow_address", ""),
            "contract_ref": deploy_result.get("contract_ref", ""),
            "network": deploy_result.get("network_id", ""),
            "status": deploy_result.get("status", "AWAITING_PAYMENT"),
        }

    async def release_escrow(self, escrow_address: str, session_id: str) -> Dict:
        """
        Release escrow funds to seller.
        Reserved for Phase 2 — not wired in this phase.
        """
        raise NotImplementedError("X402AlgorandSettlement.release_escrow is not wired in this phase")

    async def refund_escrow(self, escrow_address: str, session_id: str) -> Dict:
        """
        Refund escrow to buyer.
        Reserved for Phase 2 — not wired in this phase.
        """
        raise NotImplementedError("X402AlgorandSettlement.refund_escrow is not wired in this phase")

    @classmethod
    def get_capabilities(cls) -> SettlementCapabilities:
        """Return static capabilities for discovery APIs."""
        return SettlementCapabilities(
            provider_id="x402-algorand-testnet",
            supported_networks=["algorand-testnet"],
            supported_payment_methods=["x402"],
            supports_escrow=True,
            supports_live_transactions=True,
            simulation_mode=False,
        )
