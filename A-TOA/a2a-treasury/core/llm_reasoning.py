"""
core/llm_reasoning.py — Layer 3: LLM Advisory (Groq API).

ADVISORY ONLY. Output is a modifier signal. Never in control.
LLM NEVER sees reservation_price, budget_ceiling, or any financial threshold.
All outputs JSON-parsed and schema-validated. Modifier capped at ±0.5.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger("a2a_treasury")

LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CIRCUIT_BREAKER_THRESHOLD = 3


class LLMAdvisory(BaseModel):
    opponent_type: Literal["aggressive", "cooperative", "strategic", "bluffing"] = "strategic"
    confidence: float = Field(..., ge=0.0, le=1.0)
    bluff_probability: float = Field(..., ge=0.0, le=1.0)
    urgency_detected: bool = False
    recommended_modifier: float = Field(..., ge=-0.5, le=0.5)
    reasoning_summary: str = ""
    fallback_used: bool = False


DEFAULT_ADVISORY = LLMAdvisory(
    opponent_type="strategic",
    confidence=0.5,
    bluff_probability=0.2,
    urgency_detected=False,
    recommended_modifier=0.0,
    reasoning_summary="LLM unavailable — using default",
    fallback_used=True,
)


def _cap_modifier(value: float) -> float:
    return max(-0.5, min(0.5, value))


def _build_prompt_without_absolute_values(
    offer_history: list[dict],
    session_metadata: dict,
    flexibility_metrics: dict,
) -> str:
    """Build prompt from percentage changes only. NO absolute values, NO reservation/target."""
    lines = []
    lines.append(
        "Analyze the opponent's offer pattern. You will NEVER be told reservation "
        "prices or budget limits — analyze behavior only."
    )
    lines.append(f"Current round: {session_metadata.get('current_round', '?')}")
    lines.append(f"Max rounds: {session_metadata.get('max_rounds', '?')}")
    lines.append(f"Rounds remaining: {session_metadata.get('max_rounds', 8) - session_metadata.get('current_round', 1) + 1}")
    lines.append(f"Observer role: {session_metadata.get('agent_role', '?')}")

    opp_offers: list[tuple[int, float]] = []
    for o in offer_history:
        role = o.get("agent_role")
        # Opponent is the one we're observing (not the observer)
        observer = session_metadata.get("agent_role", "buyer")
        if role and role != observer and o.get("value") is not None:
            opp_offers.append((o.get("round", 0), float(o["value"])))

    if not opp_offers:
        lines.append("Opponent has not yet made any offers (only baseline).")
    else:
        opp_offers.sort(key=lambda x: x[0])
        for i, (rnd, val) in enumerate(opp_offers):
            if i == 0:
                lines.append(f"Round {rnd}: opponent offered [baseline].")
            else:
                prev_val = opp_offers[i - 1][1]
                if prev_val and prev_val > 0:
                    pct = ((val - prev_val) / prev_val) * 100
                    lines.append(
                        f"Round {rnd}: opponent moved {pct:+.2f}% from their previous offer."
                    )
                else:
                    lines.append(f"Round {rnd}: opponent offered new value.")
    lines.append(f"Flexibility pattern from tracker: {flexibility_metrics.get('pattern', 'unknown')}.")
    return "\n".join(lines)


class LLMAdvisor:
    """Groq-based opponent classification. Advisory only."""

    SYSTEM_PROMPT = """You are an expert negotiation analyst advising an autonomous trade agent. Analyze the opponent's offer pattern and return a structured JSON advisory. You will NEVER be told reservation prices or budget limits — analyze behavior only.

You MUST return ONLY valid JSON matching this exact schema:
{
  "opponent_type": "aggressive|cooperative|strategic|bluffing",
  "confidence": <float 0.0-1.0>,
  "bluff_probability": <float 0.0-1.0>,
  "urgency_detected": <boolean>,
  "recommended_modifier": <float -0.5 to +0.5>,
  "reasoning_summary": "<max 100 chars>"
}

recommended_modifier meaning:
  Positive → suggest slightly more generous concession
  Negative → suggest holding firmer
  0.0 → no adjustment needed

Return ONLY the JSON object. No explanation. No markdown. No code blocks. Raw JSON only."""

    def __init__(self):
        self._failure_count: dict[str, int] = {}  # session_id -> consecutive failures
        self._circuit_open: set[str] = set()

    def _session_circuit_open(self, session_id: str) -> bool:
        return session_id in self._circuit_open

    def _record_failure(self, session_id: str) -> None:
        self._failure_count[session_id] = self._failure_count.get(session_id, 0) + 1
        if self._failure_count[session_id] >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open.add(session_id)
            logger.warning("LLM_CIRCUIT_OPEN session_id=%s", session_id)

    def _record_success(self, session_id: str) -> None:
        self._failure_count[session_id] = 0

    async def classify_opponent(
        self,
        offer_history: list[dict],
        session_metadata: dict,
        flexibility_metrics: dict,
        session_id: str = "",
        db_session: Any = None,
    ) -> LLMAdvisory:
        """
        Calls Groq API. Never exposes financial thresholds.
        On any failure or circuit open: return DEFAULT_ADVISORY.
        Logs LLM_ADVISORY_USED to audit trail.
        """
        advisory: LLMAdvisory

        if not LLM_ENABLED:
            logger.debug("LLM disabled (LLM_ENABLED=false)")
            advisory = DEFAULT_ADVISORY
        elif self._session_circuit_open(session_id):
            logger.warning("LLM circuit open for session %s", session_id)
            advisory = DEFAULT_ADVISORY
        else:
            advisory = await self._call_groq(
                offer_history, session_metadata, flexibility_metrics, session_id,
            )

        # Log LLM advisory usage to audit trail
        if db_session is not None and session_id:
            try:
                from db.audit_logger import AuditLogger
                _audit = AuditLogger()
                await _audit.append(
                    entity_type="negotiation",
                    entity_id=str(session_id),
                    action="LLM_ADVISORY_USED",
                    actor_id=str(session_id),
                    payload={
                        "opponent_type": advisory.opponent_type,
                        "recommended_modifier": advisory.recommended_modifier,
                        "fallback_used": advisory.fallback_used,
                        "confidence": advisory.confidence,
                    },
                    db_session=db_session,
                )
            except Exception as e:
                logger.warning("Failed to log LLM advisory: %s", e)

        return advisory

    async def _call_groq(
        self,
        offer_history: list[dict],
        session_metadata: dict,
        flexibility_metrics: dict,
        session_id: str,
    ) -> LLMAdvisory:
        """Internal: actual Groq API call with parsing + fallback."""
        prompt = _build_prompt_without_absolute_values(
            offer_history, session_metadata, flexibility_metrics
        )

        try:
            from groq import AsyncGroq

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.warning("GROQ_API_KEY not set — using fallback")
                self._record_failure(session_id)
                return DEFAULT_ADVISORY

            client = AsyncGroq(api_key=api_key)
            model = os.getenv("GROQ_MODEL", GROQ_MODEL)

            chat_completion = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                temperature=0.3,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            raw_text = chat_completion.choices[0].message.content

            if not raw_text:
                self._record_failure(session_id)
                return DEFAULT_ADVISORY

            # Parse and validate
            text = raw_text.strip()
            # Strip markdown code block if present
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)

            modifier = float(data.get("recommended_modifier", 0.0))
            modifier = _cap_modifier(modifier)

            advisory = LLMAdvisory(
                opponent_type=data.get("opponent_type", "strategic"),
                confidence=float(data.get("confidence", 0.5)),
                bluff_probability=float(data.get("bluff_probability", 0.2)),
                urgency_detected=bool(data.get("urgency_detected", False)),
                recommended_modifier=modifier,
                reasoning_summary=(data.get("reasoning_summary") or "")[:100],
                fallback_used=False,
            )
            self._record_success(session_id)
            logger.info("Groq LLM advisory: %s (modifier: %+.3f)",
                        advisory.opponent_type, advisory.recommended_modifier)
            return advisory
        except Exception as e:
            logger.warning("Groq classify_opponent failed: %s", e)
            self._record_failure(session_id)
            return DEFAULT_ADVISORY


# Backward compatibility alias
GeminiAdvisor = LLMAdvisor
