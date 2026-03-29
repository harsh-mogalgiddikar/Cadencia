"""
core/guardrails.py — Layer 4: Hard Veto Authority.

CRITICAL RULE: The Guardrail Layer has ABSOLUTE VETO AUTHORITY.
It runs LAST, after ALL other layers. NO code path is allowed to bypass it
before an action is submitted to the state machine. Cannot be overridden by
any LLM output, any strategy decision, or any other layer.
"""
from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel


class GuardrailResult(BaseModel):
    """Result of a guardrail validation check."""
    status: Literal["CLEARED", "BLOCKED"]
    rule_violated: Optional[str] = None
    proposed_value: Optional[float] = None
    threshold: Optional[float] = None
    message: str


class GuardrailEngine:
    """Layer 4 — hard veto enforcement on all agent actions."""

    def validate_action(
        self,
        action_envelope: dict,
        valuation_snapshot: dict,
        agent_config: dict,
        session: dict,
    ) -> GuardrailResult:
        """
        Check ALL rules in sequence. Return BLOCKED on first failure.
        Return CLEARED only if ALL checks pass.

        This is a pure/synchronous method suitable for unit testing.
        """
        agent_role = action_envelope.get("agent_role", "")
        action = action_envelope.get("action", "")
        offer_value = action_envelope.get("offer_value")

        reservation_price = valuation_snapshot.get("reservation_price", 0.0)
        budget_ceiling = agent_config.get("budget_ceiling")
        max_exposure = float(agent_config.get("max_exposure", 0))

        # RULE 1: RESERVATION_BREACH (seller counter below floor)
        if agent_role == "seller" and action == "counter":
            if offer_value is not None and offer_value < reservation_price:
                return GuardrailResult(
                    status="BLOCKED",
                    rule_violated="RESERVATION_BREACH",
                    proposed_value=offer_value,
                    threshold=reservation_price,
                    message=(
                        f"Offer {offer_value} is below seller reservation "
                        f"price {reservation_price}"
                    ),
                )

        # RULE 2: BUDGET_CEILING_BREACH (buyer counter above ceiling)
        if agent_role == "buyer" and action == "counter":
            if (
                budget_ceiling is not None
                and offer_value is not None
                and offer_value > float(budget_ceiling)
            ):
                return GuardrailResult(
                    status="BLOCKED",
                    rule_violated="BUDGET_CEILING_BREACH",
                    proposed_value=offer_value,
                    threshold=float(budget_ceiling),
                    message=(
                        f"Offer {offer_value} exceeds buyer budget ceiling "
                        f"{budget_ceiling}"
                    ),
                )

        # RULE 3: MAX_EXPOSURE_BREACH (both, counter only)
        if action == "counter":
            if offer_value is not None and offer_value > max_exposure:
                return GuardrailResult(
                    status="BLOCKED",
                    rule_violated="MAX_EXPOSURE_BREACH",
                    proposed_value=offer_value,
                    threshold=max_exposure,
                    message=(
                        f"Offer {offer_value} exceeds max exposure "
                        f"{max_exposure}"
                    ),
                )

        # RULE 4: ACCEPT_BELOW_FLOOR (seller accepting too low)
        if agent_role == "seller" and action == "accept":
            if offer_value is not None and offer_value < reservation_price:
                return GuardrailResult(
                    status="BLOCKED",
                    rule_violated="ACCEPT_BELOW_FLOOR",
                    proposed_value=offer_value,
                    threshold=reservation_price,
                    message=(
                        f"Cannot accept {offer_value} — below seller "
                        f"reservation price {reservation_price}"
                    ),
                )

        # RULE 5: ACCEPT_ABOVE_CEILING (buyer accepting too high)
        if agent_role == "buyer" and action == "accept":
            if budget_ceiling is not None and offer_value is not None:
                if offer_value > float(budget_ceiling):
                    return GuardrailResult(
                        status="BLOCKED",
                        rule_violated="ACCEPT_ABOVE_CEILING",
                        proposed_value=offer_value,
                        threshold=float(budget_ceiling),
                        message=(
                            f"Cannot accept {offer_value} — exceeds buyer "
                            f"budget ceiling {budget_ceiling}"
                        ),
                    )

        # RULE 6: NEGATIVE_OR_ZERO_OFFER
        if action == "counter" and offer_value is not None:
            if offer_value <= 0:
                return GuardrailResult(
                    status="BLOCKED",
                    rule_violated="INVALID_OFFER_VALUE",
                    proposed_value=offer_value,
                    threshold=0.0,
                    message="Offer value must be positive",
                )

        # All passed
        return GuardrailResult(
            status="CLEARED",
            message="All checks passed",
        )

    async def enforce(
        self,
        action_envelope: dict,
        valuation_snapshot: dict,
        agent_config: dict,
        session: dict,
        session_id: str,
        agent_role: str,
        round_num: int,
        db_session,
        redis_client,
    ) -> GuardrailResult:
        """
        Full enforcement pipeline — called by the state machine.

        1. validate_action()
        2. If BLOCKED:
           a. INSERT to guardrail_logs
           b. Increment failure count
           c. Check if >= 3 → special POLICY_BREACH flag
        3. Return result
        """
        from db.models import GuardrailLog
        import uuid

        result = self.validate_action(
            action_envelope, valuation_snapshot, agent_config, session,
        )

        if result.status == "BLOCKED":
            # a. Persist to guardrail_logs
            log_entry = GuardrailLog(
                log_id=uuid.uuid4(),
                session_id=uuid.UUID(session_id) if isinstance(session_id, str) else session_id,
                round=round_num,
                agent_role=agent_role,
                rule_violated=result.rule_violated or "UNKNOWN",
                proposed_value=result.proposed_value,
                threshold=result.threshold,
                action_taken="BLOCKED",
            )
            db_session.add(log_entry)
            await db_session.flush()

            # b. Increment failure count
            failure_count = await redis_client.increment_failure_count(
                session_id, agent_role,
            )

            # c. Check for POLICY_BREACH
            if failure_count >= 3:
                result.rule_violated = "POLICY_BREACH"
                result.message = (
                    f"Agent {agent_role} has {failure_count} consecutive "
                    f"guardrail failures — triggering POLICY_BREACH"
                )

        return result
