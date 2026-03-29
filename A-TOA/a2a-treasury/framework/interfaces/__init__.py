"""framework/interfaces/__init__.py

Agentic Commerce Framework (ACF) — public interface exports and utilities.

Re-exports core abstract interfaces and provides compatibility helpers that
operate on A2A Agent Cards to determine protocol and settlement alignment.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .negotiation_protocol import NegotiationProtocol, ProtocolCapabilities
from .policy_engine import PolicyEngine
from .settlement_provider import (
    SettlementCapabilities,
    SettlementProvider,
)

__all__ = [
    "NegotiationProtocol",
    "ProtocolCapabilities",
    "SettlementProvider",
    "SettlementCapabilities",
    "PolicyEngine",
    "check_agent_compatibility",
]


def _extract_protocol_ids(card: Dict) -> Set[str]:
    protocols = card.get("protocols", []) or []
    ids: Set[str] = set()
    for item in protocols:
        if isinstance(item, dict):
            proto_id = item.get("id")
            if isinstance(proto_id, str):
                ids.add(proto_id)
    return ids


def _extract_list(card: Dict, key: str) -> Set[str]:
    values = card.get(key, []) or []
    return {v for v in values if isinstance(v, str)}


def check_agent_compatibility(
    agent_a_card: Dict,
    agent_b_card: Dict,
) -> Dict:
    """
    Check compatibility between two agent cards.

    Returns:
        {
            "compatible": bool,
            "shared_protocols": [...],
            "shared_settlement_networks": [...],
            "shared_payment_methods": [...],
            "incompatibility_reasons": [...],
        }
    """
    a_protocols = _extract_protocol_ids(agent_a_card)
    b_protocols = _extract_protocol_ids(agent_b_card)
    shared_protocols = sorted(a_protocols & b_protocols)

    a_networks = _extract_list(agent_a_card, "settlement_networks")
    b_networks = _extract_list(agent_b_card, "settlement_networks")
    shared_networks = sorted(a_networks & b_networks)

    a_payments = _extract_list(agent_a_card, "payment_methods")
    b_payments = _extract_list(agent_b_card, "payment_methods")
    shared_payments = sorted(a_payments & b_payments)

    compatible = bool(shared_protocols and shared_networks and shared_payments)

    incompatibility_reasons: List[str] = []
    if not shared_protocols:
        incompatibility_reasons.append(
            "No shared negotiation protocols between agents.",
        )
    if not shared_networks:
        incompatibility_reasons.append(
            "No shared settlement networks between agents.",
        )
    if not shared_payments:
        incompatibility_reasons.append(
            "No shared payment methods between agents.",
        )

    return {
        "compatible": compatible,
        "shared_protocols": shared_protocols,
        "shared_settlement_networks": shared_networks,
        "shared_payment_methods": shared_payments,
        "incompatibility_reasons": incompatibility_reasons,
    }

