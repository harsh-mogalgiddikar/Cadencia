"""framework/interfaces/negotiation_protocol.py

Agentic Commerce Framework (ACF) — negotiation protocol abstractions layer.

Defines the abstract base class for all negotiation protocol implementations
and the associated capability dataclass used for discovery and registry APIs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ProtocolCapabilities:
    """Describes the capabilities of a negotiation protocol implementation."""

    protocol_id: str
    version: str
    supports_multi_party: bool
    requires_escrow: bool
    max_rounds: int
    supported_settlement_networks: List[str]
    supported_payment_methods: List[str]


class NegotiationProtocol(ABC):
    """Abstract base for all negotiation protocols supported by the ACF layer."""

    @abstractmethod
    def get_protocol_id(self) -> str:
        """Return a string identifier e.g. 'DANP-v1', 'FixedPrice-v1'."""

    @abstractmethod
    def get_version(self) -> str:
        """Return version string e.g. '1.0.0'."""

    @abstractmethod
    def initiate(
        self,
        session_id: str,
        buyer_params: Dict,
        seller_params: Dict,
    ) -> Dict:
        """
        Start a new negotiation session.

        Returns:
            Initial state dict with keys:
            - session_id
            - status
            - opening_offer
            - metadata
        """

    @abstractmethod
    def respond(
        self,
        session_id: str,
        round_number: int,
        incoming_offer: float,
        agent_role: str,
        agent_params: Dict,
    ) -> Dict:
        """
        Process an incoming offer and return a counter or acceptance.

        Returns:
            Dict with keys:
            - action (COUNTER/ACCEPT/REJECT)
            - offer
            - reasoning
            - round
        """

    @abstractmethod
    def evaluate(self, session_id: str, current_state: Dict) -> Dict:
        """
        Evaluate current negotiation state and return FSM transition info.

        Returns:
            Dict with keys:
            - should_continue
            - recommended_action
            - risk_assessment
        """

    @abstractmethod
    def finalize(self, session_id: str, agreed_price: float) -> Dict:
        """
        Finalize and clean up negotiation state.

        Returns:
            Dict with keys:
            - session_id
            - final_price
            - rounds_taken
            - protocol_used
            - timestamp
        """

    @abstractmethod
    def supports_multi_party(self) -> bool:
        """Return True if protocol supports multi-seller auction mode."""

