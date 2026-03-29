"""api/routes/framework.py — Agentic Commerce Framework introspection APIs.

Provides read-only endpoints for discovering registered negotiation protocols
and settlement providers, as well as overall framework metadata.
Phase 3 ACF: adds FixedPrice-v1 demonstration endpoint.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from framework import FrameworkRegistry

router = APIRouter(prefix="/framework", tags=["Framework"])


@router.get("/protocols")
async def list_framework_protocols() -> dict:
    """Return list of registered negotiation protocols and capabilities."""
    items = FrameworkRegistry.list_protocols()
    protocols: list[dict] = []
    for entry in items:
        caps = entry.get("capabilities", {}) or {}
        protocols.append(
            {
                "id": caps.get("protocol_id") or entry.get("id"),
                "version": caps.get("version"),
                "supports_multi_party": bool(caps.get("supports_multi_party")),
                "requires_escrow": bool(caps.get("requires_escrow")),
                "max_rounds": caps.get("max_rounds"),
                "supported_settlement_networks": caps.get(
                    "supported_settlement_networks",
                    [],
                ),
                "supported_payment_methods": caps.get(
                    "supported_payment_methods",
                    [],
                ),
            }
        )
    return {"protocols": protocols}


@router.get("/settlement-providers")
async def list_framework_settlement_providers() -> dict:
    """Return list of registered settlement providers and capabilities."""
    items = FrameworkRegistry.list_settlement_providers()
    providers: list[dict] = []
    for entry in items:
        caps = entry.get("capabilities", {}) or {}
        providers.append(
            {
                "id": caps.get("provider_id") or entry.get("id"),
                "supported_networks": caps.get("supported_networks", []),
                "supported_payment_methods": caps.get(
                    "supported_payment_methods",
                    [],
                ),
                "supports_escrow": bool(caps.get("supports_escrow")),
                "simulation_mode": bool(caps.get("simulation_mode")),
            }
        )
    return {"providers": providers}


@router.get("/info")
async def get_framework_info() -> dict:
    """Return overall framework metadata and counts."""
    protocols = FrameworkRegistry.list_protocols()
    providers = FrameworkRegistry.list_settlement_providers()
    registered_protocol_ids = [p.get("id") for p in protocols]
    registered_provider_ids = [p.get("id") for p in providers]

    return {
        "framework": "Agentic Commerce Framework",
        "version": "2.0.0",
        "protocol_count": len(protocols),
        "settlement_provider_count": len(providers),
        "registered_protocols": registered_protocol_ids,
        "registered_settlement_providers": registered_provider_ids,
    }


# ─── Phase 3 ACF: FixedPriceProtocol demo endpoint ─────────────────────────

class FixedPriceDemoRequest(BaseModel):
    fixed_price: float = 90000
    buyer_budget: float = 95000


@router.post("/fixed-price-demo")
async def fixed_price_demo(body: FixedPriceDemoRequest) -> dict:
    """Demonstrate the FixedPriceProtocol lifecycle in one call.

    No auth required — pure in-memory demo for judges.
    """
    protocol = FrameworkRegistry.get_protocol("FixedPrice-v1")
    if protocol is None:
        return {"error": "FixedPrice-v1 protocol not registered"}

    session_id = str(uuid4())

    # 1. Initiate
    initiate_result = protocol.initiate(
        session_id,
        buyer_params={"budget_ceiling": body.buyer_budget},
        seller_params={"fixed_price": body.fixed_price},
    )

    # 2. Respond (buyer)
    respond_result = protocol.respond(
        session_id,
        round_number=1,
        incoming_offer=body.fixed_price,
        agent_role="buyer",
        agent_params={"budget_ceiling": body.buyer_budget},
    )

    # 3. Evaluate
    evaluate_result = protocol.evaluate(session_id, {})

    # 4. Finalize if accepted
    finalize_result = None
    action = respond_result.get("action", "")
    if action == "ACCEPT":
        finalize_result = protocol.finalize(session_id, body.fixed_price)

    outcome = "ACCEPTED" if action == "ACCEPT" else "REJECTED"

    return {
        "protocol": "FixedPrice-v1",
        "session_id": session_id,
        "fixed_price": body.fixed_price,
        "buyer_budget": body.buyer_budget,
        "initiate_result": initiate_result,
        "respond_result": respond_result,
        "evaluate_result": evaluate_result,
        "finalize_result": finalize_result,
        "outcome": outcome,
        "message": "FixedPrice-v1 protocol demonstration complete",
    }

