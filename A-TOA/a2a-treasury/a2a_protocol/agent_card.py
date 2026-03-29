"""
a2a_protocol/agent_card.py — A2A Agent Card generation and serving.

Generates and serves the Agent Card JSON for each activated enterprise.
This module exposes the Agentic Commerce Framework (ACF) capabilities of an
enterprise agent in the expanded agent.json schema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def generate_agent_card(
    enterprise_id: str,
    legal_name: str,
    host: str = "http://localhost:8000",
    agent_role: str | None = None,
    budget_ceiling: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate an A2A Agent Card for an activated enterprise.

    Args:
        enterprise_id: UUID of the enterprise
        legal_name: Legal name of the enterprise
        host: Base URL of the API server
        agent_role: Logical role of the agent ('buyer' or 'seller')
        budget_ceiling: Max transaction amount from agent config (if any)

    Returns:
        Agent Card dict conforming to the expanded A2A / ACF spec.
    """
    role = agent_role or "buyer"

    protocols: List[Dict[str, Any]] = [
        {
            "id": "DANP-v1",
            "version": "1.0.0",
            "supports_multi_party": True,
            "max_rounds": 10,
        },
        {
            "id": "FixedPrice-v1",
            "version": "1.0.0",
            "supports_multi_party": False,
            "max_rounds": 1,
        },
    ]

    settlement_networks: List[str] = ["algorand-testnet"]
    payment_methods: List[str] = ["x402"]

    policy_constraints: Dict[str, Any] = {
        "max_transaction": budget_ceiling if budget_ceiling is not None else None,
        "requires_escrow": True,
        "compliance_frameworks": ["FEMA", "RBI"],
    }

    capabilities: Dict[str, bool] = {
        "autonomous_negotiation": True,
        "autonomous_payment": True,
        "multi_party_auction": True,
        "policy_enforced": True,
    }

    endpoints: Dict[str, str] = {
        "agent_card": "/.well-known/agent.json",
        "negotiate": "/v1/sessions/",
        "deliver": "/v1/deliver/",
        "registry": "/v1/agents",
    }

    framework: Dict[str, str] = {
        "name": "Agentic Commerce Framework",
        "version": "1.0.0",
    }

    return {
        "agent_id": f"{enterprise_id}-agent",
        "name": f"{legal_name} Agent",
        "role": role,
        "version": "2.0.0",
        "protocols": protocols,
        "settlement_networks": settlement_networks,
        "payment_methods": payment_methods,
        "policy_constraints": policy_constraints,
        "capabilities": capabilities,
        "endpoints": endpoints,
        "framework": framework,
        "enterpriseId": str(enterprise_id),
        "kycStatus": "ACTIVE",
        "agentCardGeneratedAt": datetime.now(timezone.utc).isoformat(),
        "host": host,
    }
