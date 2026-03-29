"""framework/interfaces/settlement_provider.py

Agentic Commerce Framework (ACF) — settlement provider abstractions layer.

Defines the abstract base class for all settlement providers and the
capability dataclass used for discovery, routing, and compatibility checks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SettlementCapabilities:
    """Describes the capabilities of a settlement provider implementation."""

    provider_id: str
    supported_networks: List[str]
    supported_payment_methods: List[str]
    supports_escrow: bool
    supports_live_transactions: bool
    simulation_mode: bool


class SettlementProvider(ABC):
    """Abstract base for all settlement providers supported by the ACF layer."""

    @abstractmethod
    def get_provider_id(self) -> str:
        """Return identifier e.g. 'x402-algorand-testnet'."""

    @abstractmethod
    def get_supported_networks(self) -> List[str]:
        """Return list e.g. ['algorand-testnet', 'algorand-mainnet']."""  # noqa: D401

    @abstractmethod
    def get_supported_payment_methods(self) -> List[str]:
        """Return list e.g. ['x402', 'direct-transfer']."""  # noqa: D401

    @abstractmethod
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
        Initiate payment request. For x402 this returns a 402 challenge.

        Returns:
            Dict with keys:
            - payment_required
            - challenge
            - provider
            - network
            - amount
        """

    @abstractmethod
    def verify_payment(
        self,
        session_id: str,
        payment_token: str,
        expected_amount: float,
    ) -> Dict:
        """
        Verify and submit a signed payment token.

        Returns:
            Dict with keys:
            - verified
            - tx_id
            - network
            - amount_settled
            - idempotent
        """

    @abstractmethod
    def deploy_escrow(
        self,
        session_id: str,
        buyer_address: str,
        seller_address: str,
        amount: float,
    ) -> Dict:
        """
        Deploy an escrow contract for the session.

        Returns:
            Dict with keys:
            - escrow_address
            - contract_ref
            - network
            - status
        """

    @abstractmethod
    def release_escrow(self, escrow_address: str, session_id: str) -> Dict:
        """Release escrow funds to seller. Returns status dict."""

    @abstractmethod
    def refund_escrow(self, escrow_address: str, session_id: str) -> Dict:
        """Refund escrow to buyer. Returns status dict."""

