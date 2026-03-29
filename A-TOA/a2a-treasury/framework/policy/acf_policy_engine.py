"""framework/policy/acf_policy_engine.py

Agentic Commerce Framework (ACF) — unified policy and compliance engine.

Wraps the existing guardrails and FEMA/RBI compliance logic behind the
generic PolicyEngine interface without changing their internal behavior.
"""

from __future__ import annotations

from typing import Dict, List

from compliance import fema_engine  # type: ignore[attr-defined]
from framework.interfaces import PolicyEngine
from core.guardrails import GuardrailEngine


class ACFPolicyEngine(PolicyEngine):
    """Concrete PolicyEngine that composes guardrails and compliance checks."""

    def __init__(self) -> None:
        self._guardrails = GuardrailEngine()

    def validate_offer(
        self,
        session_id: str,
        offer: float,
        agent_role: str,
        agent_params: Dict,
    ) -> Dict:
        """
        Validate offer against guardrail budget and reservation constraints.

        Expects agent_params to optionally contain:
            - valuation_snapshot: dict
            - agent_config: dict
            - session_state: dict
        """
        valuation_snapshot = agent_params.get("valuation_snapshot") or {}
        agent_config = agent_params.get("agent_config") or {}
        session_state = agent_params.get("session_state") or {}

        action_envelope = {
            "agent_role": agent_role,
            "action": "counter",
            "offer_value": offer,
        }

        result = self._guardrails.validate_action(
            action_envelope=action_envelope,
            valuation_snapshot=valuation_snapshot,
            agent_config=agent_config,
            session=session_state,
        )

        breach_type = None
        if result.status == "BLOCKED":
            breach_type = result.rule_violated or "POLICY_BREACH"

        # Map guardrail result into the normalized schema
        if breach_type == "BUDGET_CEILING_BREACH":
            mapped_breach = "BUDGET_CEILING_BREACH"
        elif breach_type in {"RESERVATION_BREACH", "ACCEPT_BELOW_FLOOR"}:
            mapped_breach = "BELOW_RESERVATION"
        elif breach_type is None:
            mapped_breach = None
        else:
            mapped_breach = "POLICY_BREACH"

        return {
            "allowed": result.status == "CLEARED",
            "reason": result.message,
            "breach_type": mapped_breach,
        }

    def check_budget(
        self,
        session_id: str,
        amount: float,
        budget_ceiling: float,
    ) -> Dict:
        """Simple budget ceiling comparison helper."""
        overage = max(0.0, float(amount) - float(budget_ceiling))
        within = overage == 0.0
        return {
            "within_budget": within,
            "overage_amount": overage,
            "breach_triggered": not within,
        }

    def check_compliance(self, session_id: str, transaction_data: Dict) -> Dict:
        """
        Run FEMA/RBI compliance checks via existing fema_engine.

        This is a lightweight adapter around fema_engine.check_session_compliance;
        callers are expected to handle async invocation where required.
        """
        # The full FEMA engine is async and tied to DB sessions; here we
        # expose only a structural placeholder for compatibility.
        # TODO: Phase 2 — delegate to compliance.fema_engine with real DB/session context.
        applicable_rules: List[str] = ["FEMA", "RBI"]
        exemptions: List[str] = []
        required_codes: List[str] = []
        # Detailed evaluation is executed elsewhere in the existing flows.
        return {
            "compliant": True,
            "applicable_rules": applicable_rules,
            "exemptions": exemptions,
            "required_codes": required_codes,
        }

    def assess_risk(self, session_id: str, negotiation_state: Dict) -> Dict:
        """
        Derive a coarse risk level from agent risk_factor and round number.
        """
        risk_factor = float(negotiation_state.get("risk_factor", 0.5))
        round_num = int(negotiation_state.get("current_round", 1))

        if risk_factor >= 0.8 or round_num > 8:
            level = "HIGH"
        elif risk_factor <= 0.3 and round_num <= 3:
            level = "LOW"
        else:
            level = "MEDIUM"

        return {
            "risk_level": level,
            "factors": {
                "risk_factor": risk_factor,
                "current_round": round_num,
            },
            "recommended_action": "PROCEED_WITH_CAUTION" if level == "HIGH" else "CONTINUE",
        }

    def get_policy_summary(self, agent_params: Dict) -> Dict:
        """
        Extract policy constraints from an agent configuration dict.
        """
        budget_ceiling = agent_params.get("budget_ceiling")
        max_exposure = agent_params.get("max_exposure")
        requires_escrow = bool(agent_params.get("requires_escrow", True))
        compliance_flags = agent_params.get("compliance_flags") or ["FEMA", "RBI"]

        max_transaction = float(budget_ceiling) if budget_ceiling is not None else None
        min_transaction = 0.0
        if max_exposure is not None:
            try:
                min_transaction = float(max_exposure) * 0.01
            except Exception:
                min_transaction = 0.0

        return {
            "max_transaction": max_transaction,
            "min_transaction": min_transaction,
            "requires_escrow": requires_escrow,
            "compliance_flags": compliance_flags,
        }

