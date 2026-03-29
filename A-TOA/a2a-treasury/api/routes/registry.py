"""
api/routes/registry.py — Agent Registry & Discovery API.

POST   /agents/register      — register agent (JWT required)
GET    /agents               — query/discover agents (no auth)
GET    /agents/{id}          — get specific agent (no auth)
PATCH  /agents/availability  — update availability (JWT required)

Registry is Redis-backed, TTL=24h. Agents must re-register daily.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import UserContext, get_current_user
from db.database import get_db
from db.models import Enterprise
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/agents", tags=["Registry"])
logger = logging.getLogger("a2a_treasury.registry")

REGISTRY_TTL_SECONDS = 24 * 3600  # 24 hours


def _get_redis():
    from api.main import redis_manager
    return redis_manager


# ─── Request schemas ────────────────────────────────────────────────────────
class RegisterAgentRequest(BaseModel):
    service_tags: list[str] = []
    description: str = ""
    availability: str = "active"


class AvailabilityRequest(BaseModel):
    availability: str


# ─── POST /agents/register ──────────────────────────────────────────────────
@router.post("/register")
async def register_agent(
    body: RegisterAgentRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register enterprise agent in the ACF discovery registry (JWT required)."""
    import uuid as _uuid
    eid = user.enterprise_id
    try:
        enterprise_uuid = _uuid.UUID(eid)
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid enterprise_id in token")

    # Load enterprise
    result = await db.execute(
        select(Enterprise).where(Enterprise.enterprise_id == enterprise_uuid)
    )
    enterprise = result.scalar_one_or_none()
    if not enterprise:
        raise HTTPException(404, "Enterprise not found")

    agent_card = enterprise.agent_card_data or {}

    # Extract protocol/settlement/payment from card
    protocols = agent_card.get("protocols", [])
    protocol = protocols[0].get("id") if protocols and isinstance(protocols[0], dict) else "DANP-v1"
    networks = agent_card.get("settlement_networks", [])
    settlement_network = networks[0] if networks else "algorand-testnet"
    payments = agent_card.get("payment_methods", [])
    payment_method = payments[0] if payments else "x402"

    now = datetime.now(timezone.utc).isoformat()

    redis = _get_redis()
    registry_key = f"agent_registry:{eid}"
    registry_data = {
        "enterprise_id": eid,
        "legal_name": enterprise.legal_name or "",
        "agent_card": json.dumps(agent_card),
        "service_tags": json.dumps(body.service_tags),
        "description": body.description,
        "availability": body.availability,
        "registered_at": now,
        "protocol": protocol,
        "settlement_network": settlement_network,
        "payment_method": payment_method,
    }

    await redis.client.hset(registry_key, mapping=registry_data)
    await redis.client.expire(registry_key, REGISTRY_TTL_SECONDS)
    await redis.client.sadd("agent_registry:index", eid)

    logger.info("Agent registered: %s (%s)", enterprise.legal_name, eid[:8])

    return {
        "registered": True,
        "enterprise_id": eid,
        "agent_id": f"{eid}-agent",
        "service_tags": body.service_tags,
        "expires_in_hours": 24,
        "message": "Agent registered in ACF discovery registry",
    }


# ─── GET /agents ────────────────────────────────────────────────────────────
@router.get("/")
async def list_agents(
    service: str | None = Query(None, description="Filter by service tag"),
    protocol: str | None = Query(None, description="Filter by protocol ID"),
    network: str | None = Query(None, description="Filter by settlement network"),
    availability: str | None = Query(None, description="Filter by availability status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """Query the agent registry. All query params are optional. No auth required."""
    redis = _get_redis()
    members = await redis.client.smembers("agent_registry:index")
    if not members:
        return {
            "agents": [],
            "total": 0,
            "filters_applied": _build_filters(service, protocol, network, availability),
        }

    agents = []
    for eid in members:
        data = await redis.client.hgetall(f"agent_registry:{eid}")
        if not data:
            # Entry expired — clean up index
            await redis.client.srem("agent_registry:index", eid)
            continue

        # Parse stored JSON fields
        service_tags = json.loads(data.get("service_tags", "[]"))

        # Apply filters (AND conditions)
        if service and service.lower() not in [t.lower() for t in service_tags]:
            continue
        if protocol and data.get("protocol", "").lower() != protocol.lower():
            continue
        if network and data.get("settlement_network", "").lower() != network.lower():
            continue
        if availability and data.get("availability", "").lower() != availability.lower():
            continue

        agents.append({
            "enterprise_id": data.get("enterprise_id", eid),
            "agent_id": f"{data.get('enterprise_id', eid)}-agent",
            "legal_name": data.get("legal_name", ""),
            "description": data.get("description", ""),
            "service_tags": service_tags,
            "protocol": data.get("protocol", ""),
            "settlement_network": data.get("settlement_network", ""),
            "payment_method": data.get("payment_method", ""),
            "availability": data.get("availability", ""),
            "registered_at": data.get("registered_at", ""),
        })

        if len(agents) >= limit:
            break

    return {
        "agents": agents,
        "total": len(agents),
        "filters_applied": _build_filters(service, protocol, network, availability),
    }


def _build_filters(service, protocol, network, availability):
    f = {}
    if service:
        f["service"] = service
    if protocol:
        f["protocol"] = protocol
    if network:
        f["network"] = network
    if availability:
        f["availability"] = availability
    return f


# ─── GET /agents/{enterprise_id} ───────────────────────────────────────────
@router.get("/{enterprise_id}")
async def get_agent(enterprise_id: str):
    """Returns full registry entry for a specific enterprise agent. No auth required."""
    redis = _get_redis()
    data = await redis.client.hgetall(f"agent_registry:{enterprise_id}")
    if not data:
        raise HTTPException(404, "Agent not registered in discovery registry")

    service_tags = json.loads(data.get("service_tags", "[]"))
    agent_card = json.loads(data.get("agent_card", "{}"))

    return {
        "enterprise_id": data.get("enterprise_id", enterprise_id),
        "agent_id": f"{data.get('enterprise_id', enterprise_id)}-agent",
        "legal_name": data.get("legal_name", ""),
        "description": data.get("description", ""),
        "service_tags": service_tags,
        "protocol": data.get("protocol", ""),
        "settlement_network": data.get("settlement_network", ""),
        "payment_method": data.get("payment_method", ""),
        "availability": data.get("availability", ""),
        "registered_at": data.get("registered_at", ""),
        "agent_card": agent_card,
    }


# ─── PATCH /agents/availability ─────────────────────────────────────────────
@router.patch("/availability")
async def update_availability(
    body: AvailabilityRequest,
    user: UserContext = Depends(get_current_user),
):
    """Update availability status for the authenticated enterprise's agent (JWT required)."""
    if body.availability not in ("active", "busy", "inactive"):
        raise HTTPException(400, "availability must be 'active', 'busy', or 'inactive'")

    eid = user.enterprise_id
    redis = _get_redis()

    exists = await redis.client.exists(f"agent_registry:{eid}")
    if not exists:
        raise HTTPException(404, "Agent not registered. Call POST /agents/register first.")

    await redis.client.hset(f"agent_registry:{eid}", "availability", body.availability)
    logger.info("Agent availability updated: %s → %s", eid[:8], body.availability)

    data = await redis.client.hgetall(f"agent_registry:{eid}")
    service_tags = json.loads(data.get("service_tags", "[]"))

    return {
        "enterprise_id": eid,
        "agent_id": f"{eid}-agent",
        "availability": body.availability,
        "service_tags": service_tags,
        "message": f"Agent availability updated to {body.availability}",
    }
