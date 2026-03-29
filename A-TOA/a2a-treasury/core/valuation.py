"""
core/valuation.py — Layer 1: Deterministic Valuation Engine.

CRITICAL RULE: This module is PURELY DETERMINISTIC MATH.
No LLM calls. No Redis. No DB. No randomness. No external I/O of any kind.
All inputs come from agent_configs. All outputs are floats.

This is the ONLY module that computes financial thresholds. No other module
is ever permitted to compute reservation_price, budget_ceiling, or target_price.
"""
from __future__ import annotations

from datetime import datetime, timezone


def compute_reservation_price(
    intrinsic_value: float,
    risk_factor: float,
    agent_role: str,
) -> float:
    """
    Compute the absolute price boundary.

    Buyer:  reservation_price = intrinsic_value * (1 + risk_factor)
            This is the absolute ceiling — buyer must never offer above this.
    Seller: reservation_price = intrinsic_value * (1 - risk_factor)
            This is the absolute floor — seller must never accept below this.
    """
    if agent_role == "buyer":
        return intrinsic_value * (1.0 + risk_factor)
    elif agent_role == "seller":
        return intrinsic_value * (1.0 - risk_factor)
    else:
        raise ValueError(f"Invalid agent_role: {agent_role}. Must be 'buyer' or 'seller'.")


def compute_target_price(
    intrinsic_value: float,
    negotiation_margin: float,
    agent_role: str,
) -> float:
    """
    Compute the aspiration price — best realistic outcome.

    Buyer:  target_price = intrinsic_value * (1 - negotiation_margin)
    Seller: target_price = intrinsic_value * (1 + negotiation_margin)
    """
    if agent_role == "buyer":
        return intrinsic_value * (1.0 - negotiation_margin)
    elif agent_role == "seller":
        return intrinsic_value * (1.0 + negotiation_margin)
    else:
        raise ValueError(f"Invalid agent_role: {agent_role}. Must be 'buyer' or 'seller'.")


def compute_utility_score(
    offer_value: float,
    reservation_price: float,
    target_price: float,
    agent_role: str,
) -> float:
    """
    Normalized utility in [0.0, 1.0].

    For BUYER:
      - offer_value == target_price  → utility = 1.0  (paying less is better)
      - offer_value == reservation_price → utility = 0.0 (at ceiling)
      utility = (reservation_price - offer_value) / (reservation_price - target_price)

    For SELLER:
      - offer_value == target_price  → utility = 1.0  (selling high is better)
      - offer_value == reservation_price → utility = 0.0 (at floor)
      utility = (offer_value - reservation_price) / (target_price - reservation_price)
    """
    if agent_role == "buyer":
        denominator = reservation_price - target_price
        if denominator == 0:
            return 0.0
        raw = (reservation_price - offer_value) / denominator
    elif agent_role == "seller":
        denominator = target_price - reservation_price
        if denominator == 0:
            return 0.0
        raw = (offer_value - reservation_price) / denominator
    else:
        raise ValueError(f"Invalid agent_role: {agent_role}. Must be 'buyer' or 'seller'.")

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, raw))


def compute_opening_anchor(
    target_price: float,
    concession_curve: dict,
    agent_role: str,
) -> float:
    """
    The opening anchor — first offer intentionally beyond target_price.

    Buyer:  anchor = target_price / (1 + concession_curve["1"])
            (anchors BELOW target to avoid revealing ceiling)
    Seller: anchor = target_price * (1 + concession_curve["1"])
            (anchors ABOVE target to inflate starting point)
    """
    first_concession = float(concession_curve.get("1", 0.05))

    if agent_role == "buyer":
        return target_price / (1.0 + first_concession)
    elif agent_role == "seller":
        return target_price * (1.0 + first_concession)
    else:
        raise ValueError(f"Invalid agent_role: {agent_role}. Must be 'buyer' or 'seller'.")


def build_valuation_snapshot(agent_config: dict) -> dict:
    """
    Compute all valuation metrics at once. Returns an immutable snapshot.
    Computed ONCE at session creation and stored in Redis. NEVER recomputed.

    Args:
        agent_config: dict with keys: intrinsic_value, risk_factor,
                      negotiation_margin, concession_curve, budget_ceiling,
                      max_exposure, agent_role

    Returns:
        Snapshot dict with all computed thresholds.
    """
    intrinsic = float(agent_config["intrinsic_value"])
    risk = float(agent_config["risk_factor"])
    margin = float(agent_config["negotiation_margin"])
    role = agent_config["agent_role"]
    curve = agent_config["concession_curve"]
    ceiling = agent_config.get("budget_ceiling")
    max_exp = float(agent_config["max_exposure"])

    reservation = compute_reservation_price(intrinsic, risk, role)
    target = compute_target_price(intrinsic, margin, role)
    anchor = compute_opening_anchor(target, curve, role)

    return {
        "reservation_price": reservation,
        "target_price": target,
        "utility_score_at_reservation": 0.0,
        "utility_score_at_target": 1.0,
        "opening_anchor": anchor,
        "budget_ceiling": float(ceiling) if ceiling is not None else None,
        "max_exposure": max_exp,
        "agent_role": role,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_utility_for_offer(
    offer_value: float,
    snapshot: dict,
) -> float:
    """
    Convenience: compute utility for any offer using a pre-computed snapshot.
    """
    return compute_utility_score(
        offer_value=offer_value,
        reservation_price=snapshot["reservation_price"],
        target_price=snapshot["target_price"],
        agent_role=snapshot["agent_role"],
    )
