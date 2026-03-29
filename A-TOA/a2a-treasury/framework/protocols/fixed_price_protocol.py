"""framework/protocols/fixed_price_protocol.py

FixedPriceProtocol — NegotiationProtocol implementation.
Seller posts a fixed price. Buyer accepts or rejects. No rounds, no concession.
Demonstrates framework extensibility — second protocol alongside DANP-v1.
Layer: Protocol Layer — Agentic Commerce Framework
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from framework.interfaces import NegotiationProtocol, ProtocolCapabilities

# In-memory session state (no DB needed — self-contained protocol)
_sessions: dict[str, dict] = {}


class FixedPriceProtocol(NegotiationProtocol):
    """Fixed-price negotiation: seller posts a price, buyer accepts or rejects."""

    def get_protocol_id(self) -> str:
        return "FixedPrice-v1"

    def get_version(self) -> str:
        return "1.0.0"

    def supports_multi_party(self) -> bool:
        return False

    @classmethod
    def get_capabilities(cls) -> ProtocolCapabilities:
        """Return static capabilities for discovery APIs."""
        return ProtocolCapabilities(
            protocol_id="FixedPrice-v1",
            version="1.0.0",
            supports_multi_party=False,
            requires_escrow=False,
            max_rounds=1,
            supported_settlement_networks=["algorand-testnet"],
            supported_payment_methods=["x402", "direct-transfer"],
        )

    def initiate(
        self,
        session_id: str,
        buyer_params: Dict,
        seller_params: Dict,
    ) -> Dict:
        """Start a FixedPrice session. seller_params must include 'fixed_price'."""
        fixed_price = seller_params.get("fixed_price")
        if fixed_price is None:
            raise ValueError("seller_params must include 'fixed_price'")

        buyer_budget = buyer_params.get("budget_ceiling", float("inf"))

        _sessions[session_id] = {
            "fixed_price": fixed_price,
            "buyer_budget": buyer_budget,
            "status": "PENDING_ACCEPTANCE",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "session_id": session_id,
            "status": "PENDING_ACCEPTANCE",
            "opening_offer": fixed_price,
            "metadata": {"protocol": "FixedPrice-v1", "max_rounds": 1},
        }

    def respond(
        self,
        session_id: str,
        round_number: int,
        incoming_offer: float,
        agent_role: str,
        agent_params: Dict,
    ) -> Dict:
        """Buyer responds to the fixed price — accept or reject."""
        if agent_role != "buyer":
            raise ValueError("Only buyer responds in FixedPrice protocol")

        state = _sessions.get(session_id, {})
        fixed_price = state.get("fixed_price", incoming_offer)
        buyer_budget = state.get("buyer_budget", float("inf"))

        if fixed_price <= buyer_budget:
            if session_id in _sessions:
                _sessions[session_id]["status"] = "ACCEPTED"
            return {
                "action": "ACCEPT",
                "offer": fixed_price,
                "reasoning": "Fixed price within budget",
                "round": 1,
            }
        else:
            if session_id in _sessions:
                _sessions[session_id]["status"] = "REJECTED"
            return {
                "action": "REJECT",
                "offer": None,
                "reasoning": "Fixed price exceeds buyer budget",
                "round": 1,
            }

    def evaluate(self, session_id: str, current_state: Dict) -> Dict:
        """Evaluate whether the FixedPrice session should continue."""
        state = _sessions.get(session_id, {})
        status = state.get("status", "UNKNOWN")

        return {
            "should_continue": status == "PENDING_ACCEPTANCE",
            "recommended_action": (
                "AWAIT_BUYER_RESPONSE"
                if status == "PENDING_ACCEPTANCE"
                else "FINALIZE"
            ),
            "risk_assessment": "LOW",
        }

    def finalize(self, session_id: str, agreed_price: float) -> Dict:
        """Finalize and clean up FixedPrice session state."""
        _sessions.pop(session_id, None)

        return {
            "session_id": session_id,
            "final_price": agreed_price,
            "rounds_taken": 1,
            "protocol_used": "FixedPrice-v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
