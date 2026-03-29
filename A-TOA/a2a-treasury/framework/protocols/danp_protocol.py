"""framework/protocols/danp_protocol.py

Agentic Commerce Framework (ACF) — DANP negotiation protocol wrapper.

Wraps the existing DANP finite state machine and neutral negotiation engine
behind the generic NegotiationProtocol interface without changing core logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from framework.interfaces import NegotiationProtocol, ProtocolCapabilities


class DANPProtocol(NegotiationProtocol):
    """Concrete NegotiationProtocol implementation for the DANP FSM."""

    def __init__(self) -> None:
        # Import lazily to avoid circular imports at module load time.
        from core.state_machine import DANPStateMachine

        self._state_machine = DANPStateMachine()

    def get_protocol_id(self) -> str:
        return "DANP-v1"

    def get_version(self) -> str:
        return "1.0.0"

    def initiate(
        self,
        session_id: str,
        buyer_params: Dict,
        seller_params: Dict,
    ) -> Dict:
        """
        Start a new negotiation session using the existing DANPStateMachine.

        Note:
            The underlying state machine is asynchronous and requires a DB
            session and Redis client. These must be provided via the
            buyer_params dict:
                - db_session: AsyncSession
                - redis_client: RedisSessionManager or compatible
                - milestone_template_id
                - timeout_seconds
                - max_rounds
        """
        db_session = buyer_params.get("db_session")
        redis_client = buyer_params.get("redis_client")
        buyer_enterprise_id = buyer_params.get("enterprise_id")
        seller_enterprise_id = seller_params.get("enterprise_id")
        initial_offer_value = buyer_params.get("initial_offer_value")
        milestone_template_id = buyer_params.get("milestone_template_id")
        timeout_seconds = buyer_params.get("timeout_seconds", 3600)
        max_rounds = buyer_params.get("max_rounds", 10)

        if db_session is None or redis_client is None:
            raise RuntimeError("DANPProtocol.initiate requires db_session and redis_client in buyer_params")

        # The actual asynchronous call must be awaited by the caller; this
        # method is a thin synchronous facade that returns the expected
        # response shape when given the already-created result.
        if "existing_result" in buyer_params:
            result = buyer_params["existing_result"]
        else:
            # For existing code paths, sessions are created elsewhere (e.g. API
            # routes). In those cases, this method can be given an
            # existing_result instead of invoking the FSM directly.
            raise RuntimeError("DANPProtocol.initiate expects 'existing_result' in buyer_params for now")

        return {
            "session_id": result["session_id"],
            "status": result["status"],
            "opening_offer": initial_offer_value,
            "metadata": {
                "buyer_enterprise_id": result.get("buyer_enterprise_id"),
                "seller_enterprise_id": result.get("seller_enterprise_id"),
                "timeout_at": result.get("timeout_at"),
                "max_rounds": result.get("max_rounds"),
                "protocol_id": self.get_protocol_id(),
            },
        }

    def respond(
        self,
        session_id: str,
        round_number: int,
        incoming_offer: float,
        agent_role: str,
        agent_params: Dict,
    ) -> Dict:
        """
        Wrap a DANP state transition for a single agent action.

        This method expects agent_params to include a pre-built action dict
        and the latest process_action result from the state machine, since
        the core transition logic remains in core.state_machine.DANPStateMachine.
        """
        action = agent_params.get("action")
        fsm_result = agent_params.get("fsm_result")

        if not isinstance(action, dict) or not isinstance(fsm_result, dict):
            raise RuntimeError("DANPProtocol.respond expects 'action' and 'fsm_result' in agent_params")

        last_action = fsm_result.get("last_action", action.get("action"))
        offer_value = fsm_result.get("offer_value", incoming_offer)

        return {
            "action": (last_action or "").upper(),
            "offer": offer_value,
            "reasoning": agent_params.get("reasoning"),
            "round": fsm_result.get("current_round", round_number),
        }

    def evaluate(self, session_id: str, current_state: Dict) -> Dict:
        """
        Evaluate current DANP state and return continuation recommendation.

        This does not alter the underlying FSM; it only inspects the state
        dict as maintained by Redis and Postgres.
        """
        status = current_state.get("status")
        max_rounds = current_state.get("max_rounds", 0)
        current_round = current_state.get("current_round", 0)

        should_continue = status not in {"AGREED", "WALKAWAY", "TIMEOUT", "ROUND_LIMIT", "STALLED", "POLICY_BREACH"}
        if current_round >= max_rounds:
            should_continue = False

        recommended_action = "CONTINUE" if should_continue else "STOP"
        risk_level = "MEDIUM"
        if status == "POLICY_BREACH":
            risk_level = "HIGH"
        elif status == "AGREED":
            risk_level = "LOW"

        return {
            "should_continue": should_continue,
            "recommended_action": recommended_action,
            "risk_assessment": {
                "risk_level": risk_level,
                "status": status,
                "current_round": current_round,
                "max_rounds": max_rounds,
            },
        }

    def finalize(self, session_id: str, agreed_price: float) -> Dict:
        """
        Finalize negotiation metadata.

        Core cleanup for DANP is already handled inside the state machine and
        neutral agent; this method simply returns a standardized summary.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "session_id": session_id,
            "final_price": agreed_price,
            "rounds_taken": None,
            "protocol_used": self.get_protocol_id(),
            "timestamp": timestamp,
        }

    def supports_multi_party(self) -> bool:
        return True

    @classmethod
    def get_capabilities(cls) -> ProtocolCapabilities:
        """Return static capabilities for the DANP protocol."""
        return ProtocolCapabilities(
            protocol_id="DANP-v1",
            version="1.0.0",
            supports_multi_party=True,
            requires_escrow=True,
            max_rounds=10,
            supported_settlement_networks=["algorand-testnet"],
            supported_payment_methods=["x402"],
        )

