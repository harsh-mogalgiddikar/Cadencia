"""
core/strategy.py — Layer 2: Game-Theoretic Strategy Engine.

CRITICAL RULE: This module is DETERMINISTIC. No LLM calls. No I/O.
All inputs come from agent_config + valuation_snapshot + session state.
Layer 1 owns all financial math; Layer 2 decides HOW to move toward target.
"""
from __future__ import annotations

from core.valuation import compute_utility_for_offer


def compute_next_offer(
    current_round: int,
    last_own_offer: float,
    last_opponent_offer: float | None,
    prev_opponent_offer: float | None,
    valuation_snapshot: dict,
    agent_config: dict,
    flexibility_score: float,
    llm_modifier: float,
    agent_role: str,
    rounds_remaining: int,
) -> dict:
    """
    Returns:
    {
      "offer_value": float,
      "strategy_tag": str,
      "confidence": float,
      "rationale": str
    }
    """
    concession_curve = agent_config.get("concession_curve") or {}
    # STEP 1 — Base concession amount
    concession_fraction = concession_curve.get(str(current_round), 0.005)
    if isinstance(concession_fraction, (int, float)):
        concession_fraction = float(concession_fraction)
    else:
        concession_fraction = 0.005

    # STEP 2 — Tit-for-tat modifier
    tit_for_tat_bonus = 0.0
    if last_opponent_offer is not None and prev_opponent_offer is not None and prev_opponent_offer > 0:
        opponent_concession = abs(last_opponent_offer - prev_opponent_offer)
        if opponent_concession > 0.02 * last_opponent_offer:
            tit_for_tat_bonus = 0.005
        elif opponent_concession < 0.005 * last_opponent_offer:
            tit_for_tat_bonus = -0.002

    # STEP 3 — Flexibility modifier
    flexibility_mod = (flexibility_score - 0.5) * 0.01

    # STEP 4 — LLM modifier (advisory cap ±1%)
    llm_mod = max(-0.01, min(0.01, (llm_modifier or 0.0) * 0.02))

    # STEP 5 — Deadline pressure
    if rounds_remaining <= 2:
        deadline_factor = 1.3
        strategy_tag = "deadline_push"
    else:
        deadline_factor = 1.0
        strategy_tag = "concede"

    # STEP 6 — Total concession fraction
    total_fraction = (
        concession_fraction + tit_for_tat_bonus + flexibility_mod + llm_mod
    ) * deadline_factor
    total_fraction = max(0.001, min(0.15, total_fraction))

    # STEP 7 — Compute offer value
    reservation_price = valuation_snapshot["reservation_price"]
    target_price = valuation_snapshot["target_price"]
    budget_ceiling = valuation_snapshot.get("budget_ceiling")

    if agent_role == "buyer":
        offer_value = last_own_offer * (1.0 + total_fraction)
        cap = budget_ceiling if budget_ceiling is not None else reservation_price
        offer_value = min(offer_value, cap)
    else:
        offer_value = last_own_offer * (1.0 - total_fraction)
        offer_value = max(offer_value, reservation_price)

    # STEP 8 — Determine strategy_tag
    if current_round == 1:
        strategy_tag = "anchor"
    elif total_fraction < 0.003:
        strategy_tag = "hold"
    elif rounds_remaining <= 2:
        strategy_tag = "deadline_push"
    else:
        strategy_tag = "concede"

    # STEP 9 — Confidence
    max_distance = abs(reservation_price - target_price)
    if max_distance <= 0:
        confidence = 0.5
    else:
        distance_to_target = abs(offer_value - target_price)
        confidence = 1.0 - (distance_to_target / max_distance)
    confidence = max(0.3, min(0.99, confidence))

    # STEP 10 — Round to 2 decimal places
    offer_value = round(offer_value, 2)

    return {
        "offer_value": offer_value,
        "strategy_tag": strategy_tag,
        "confidence": confidence,
        "rationale": f"round={current_round} tag={strategy_tag}",
    }


def should_accept(
    opponent_offer: float,
    valuation_snapshot: dict,
    current_round: int,
    max_rounds: int,
    flexibility_score: float,
) -> bool:
    """Returns True if the agent should accept the opponent's offer."""
    target_price = valuation_snapshot["target_price"]
    reservation_price = valuation_snapshot["reservation_price"]
    agent_role = valuation_snapshot["agent_role"]
    budget_ceiling = valuation_snapshot.get("budget_ceiling")

    # NEVER accept if utility < 0 (beyond reservation)
    utility = compute_utility_for_offer(opponent_offer, valuation_snapshot)
    if utility < 0.0:
        return False

    # 1. Within 0.5% of target
    if target_price and abs(opponent_offer - target_price) / target_price < 0.005:
        return True

    # 2. Last round and within guardrail bounds
    rounds_remaining = max_rounds - current_round
    if rounds_remaining <= 1:
        if agent_role == "buyer":
            if budget_ceiling is not None and opponent_offer <= budget_ceiling:
                return True
            if opponent_offer <= reservation_price:
                return True
        else:
            if opponent_offer >= reservation_price:
                return True

    # 3. Utility >= 0.85
    if utility >= 0.85:
        return True

    # 4. Cooperative opponent and reasonably good offer
    if flexibility_score > 0.7 and utility >= 0.70:
        return True

    return False


def compute_opening_offer(
    valuation_snapshot: dict,
    agent_config: dict,
    agent_role: str,
) -> dict:
    """Compute the agent's very first offer (round 1)."""
    opening_anchor = valuation_snapshot["opening_anchor"]
    target_price = valuation_snapshot["target_price"]
    reservation_price = valuation_snapshot["reservation_price"]
    budget_ceiling = valuation_snapshot.get("budget_ceiling")

    offer_value = opening_anchor
    if agent_role == "buyer" and budget_ceiling is not None:
        offer_value = min(offer_value, budget_ceiling)
    elif agent_role == "seller":
        offer_value = max(offer_value, reservation_price)

    offer_value = round(offer_value, 2)
    max_distance = abs(reservation_price - target_price)
    if max_distance <= 0:
        confidence = 0.5
    else:
        distance_to_target = abs(offer_value - target_price)
        confidence = 1.0 - (distance_to_target / max_distance)
    confidence = max(0.3, min(0.99, confidence))

    return {
        "offer_value": offer_value,
        "strategy_tag": "anchor",
        "confidence": confidence,
        "rationale": "Opening anchor",
    }


def should_reject(
    opponent_offer: float,
    valuation_snapshot: dict,
    current_round: int,
    consecutive_failures: int,
) -> bool:
    """Returns True if agent should hard reject (WALKAWAY)."""
    reservation_price = valuation_snapshot["reservation_price"]
    agent_role = valuation_snapshot["agent_role"]
    budget_ceiling = valuation_snapshot.get("budget_ceiling")

    # 1. Opponent offer violates guardrail by more than 5%
    if agent_role == "buyer" and budget_ceiling is not None:
        if opponent_offer > budget_ceiling * 1.05:
            return True
    if agent_role == "seller":
        if opponent_offer < reservation_price * 0.95:
            return True

    # 2. Consecutive failures >= 2 and opponent not moving (caller must pass stall info)
    if consecutive_failures >= 2:
        # Caller should combine with "opponent_offer unchanged for 2 rounds"
        pass  # Rare; rely on caller to pass consecutive_failures when relevant

    return False
