"""framework/interfaces/policy_engine.py

Agentic Commerce Framework (ACF) — policy and guardrail abstractions layer.

Defines the abstract base class for policy enforcement engines that unify
budget, guardrail, and regulatory compliance checks across protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class PolicyEngine(ABC):
    """Abstract base for all policy engines used by the ACF layer."""

    @abstractmethod
    def validate_offer(
        self,
        session_id: str,
        offer: float,
        agent_role: str,
        agent_params: Dict,
    ) -> Dict:
        """
        Validate an offer against agent policy parameters.

        Returns:
            Dict with keys:
            - allowed
            - reason
            - breach_type (None if allowed)

        breach_type options:
            'BUDGET_CEILING_BREACH', 'BELOW_RESERVATION', 'POLICY_BREACH', None
        """

    @abstractmethod
    def check_budget(
        self,
        session_id: str,
        amount: float,
        budget_ceiling: float,
    ) -> Dict:
        """
        Check if amount exceeds budget ceiling.

        Returns:
            Dict with keys:
            - within_budget
            - overage_amount
            - breach_triggered
        """

    @abstractmethod
    def check_compliance(self, session_id: str, transaction_data: Dict) -> Dict:
        """
        Run compliance checks (FEMA, RBI, etc.).

        Returns:
            Dict with keys:
            - compliant
            - applicable_rules
            - exemptions
            - required_codes
        """

    @abstractmethod
    def assess_risk(self, session_id: str, negotiation_state: Dict) -> Dict:
        """
        Assess risk level of current negotiation state.

        Returns:
            Dict with keys:
            - risk_level (LOW/MEDIUM/HIGH)
            - factors
            - recommended_action
        """

    @abstractmethod
    def get_policy_summary(self, agent_params: Dict) -> Dict:
        """
        Return a summary of policy constraints for an agent (for handshake use).

        Returns:
            Dict with keys:
            - max_transaction
            - min_transaction
            - requires_escrow
            - compliance_flags
        """

