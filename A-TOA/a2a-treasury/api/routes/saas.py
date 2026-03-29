"""
api/routes/saas.py — B2B SaaS endpoints: plans, subscriptions, and API keys.

Design goals:
- Keep existing ACF negotiation, escrow, FX, and compliance behavior exactly as-is.
- Add a thin SaaS layer on top: tenants (enterprises) select plans and integrate via API keys.
- Do NOT enforce hard billing in the core FSM; use soft checks and rate limits instead.
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import UserContext, require_admin, require_any_role
from api.schemas.saas import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyWithSecretResponse,
    SubscriptionCreate,
    SubscriptionPlanCreate,
    SubscriptionPlanListResponse,
    SubscriptionPlanResponse,
    SubscriptionResponse,
)
from db.database import get_db
from db.models import ApiKey, Enterprise, Subscription, SubscriptionPlan

router = APIRouter(prefix="/saas", tags=["SaaS"])


def _hash_api_key(raw: str) -> str:
    import hashlib

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _make_api_key() -> tuple[str, str]:
    """
    Returns (prefix, full_key). The full key is shown once to the caller, only the
    prefix and hash are stored in DB for security.
    """
    raw = secrets.token_urlsafe(40)
    prefix = raw[:10]
    return prefix, raw


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ─── Subscription plans (catalog) ──────────────────────────────────────────────
@router.post(
    "/plans",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan(
    body: SubscriptionPlanCreate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Platform admin — create a subscription plan."""
    # For now we treat any admin as allowed; later we can introduce platform-level roles.
    existing = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == body.name),
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "Plan with this name already exists")

    plan = SubscriptionPlan(
        plan_id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        monthly_price_usd=body.monthly_price_usd,
        max_sessions_per_month=body.max_sessions_per_month,
        max_concurrent_sessions=body.max_concurrent_sessions,
        max_enterprises_per_group=body.max_enterprises_per_group,
        features=body.features,
        active=True,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return SubscriptionPlanResponse(
        plan_id=str(plan.plan_id),
        name=plan.name,
        description=plan.description,
        monthly_price_usd=float(plan.monthly_price_usd),
        max_sessions_per_month=plan.max_sessions_per_month,
        max_concurrent_sessions=plan.max_concurrent_sessions,
        max_enterprises_per_group=plan.max_enterprises_per_group,
        features=plan.features or {},
        active=plan.active,
    )


@router.get("/plans", response_model=SubscriptionPlanListResponse)
async def list_plans(
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Any authenticated user — list active plans."""
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.active == True),
    )
    plans: Iterable[SubscriptionPlan] = result.scalars().all()
    return SubscriptionPlanListResponse(
        items=[
            SubscriptionPlanResponse(
                plan_id=str(p.plan_id),
                name=p.name,
                description=p.description,
                monthly_price_usd=float(p.monthly_price_usd),
                max_sessions_per_month=p.max_sessions_per_month,
                max_concurrent_sessions=p.max_concurrent_sessions,
                max_enterprises_per_group=p.max_enterprises_per_group,
                features=p.features or {},
                active=p.active,
            )
            for p in plans
        ]
    )


# ─── Subscriptions (enterprise ↔ plan) ────────────────────────────────────────
@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    body: SubscriptionCreate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Enterprise admin — attach current enterprise to a plan.
    Billing is external; this endpoint reflects the current subscription state.
    """
    # Ensure plan exists and is active
    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.plan_id == uuid.UUID(body.plan_id),
            SubscriptionPlan.active == True,
        ),
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(404, "Plan not found or inactive")

    # Ensure enterprise exists
    ent_res = await db.execute(
        select(Enterprise).where(Enterprise.enterprise_id == admin.enterprise_id),
    )
    ent = ent_res.scalar_one_or_none()
    if ent is None:
        raise HTTPException(404, "Enterprise not found")

    # Deactivate any existing active subscriptions
    await db.execute(
        select(Subscription).where(
            Subscription.enterprise_id == admin.enterprise_id,
            Subscription.status == "active",
        )
    )

    sub = Subscription(
        subscription_id=uuid.uuid4(),
        enterprise_id=admin.enterprise_id,
        plan_id=plan.plan_id,
        status="active",
        current_period_start=_now_utc(),
        current_period_end=body.current_period_end,
        seat_count=body.seat_count,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return SubscriptionResponse(
        subscription_id=str(sub.subscription_id),
        enterprise_id=str(sub.enterprise_id),
        plan_id=str(sub.plan_id),
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        seat_count=sub.seat_count,
    )


@router.get("/subscriptions/me", response_model=SubscriptionResponse | None)
async def get_my_subscription(
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Return the current active subscription for the caller's enterprise, if any."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.enterprise_id == user.enterprise_id,
            Subscription.status == "active",
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return None
    return SubscriptionResponse(
        subscription_id=str(sub.subscription_id),
        enterprise_id=str(sub.enterprise_id),
        plan_id=str(sub.plan_id),
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        seat_count=sub.seat_count,
    )


# ─── API Keys ─────────────────────────────────────────────────────────────────
@router.post(
    "/api-keys",
    response_model=ApiKeyWithSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    body: ApiKeyCreate,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Enterprise admin — create an API key for integrations.
    The full secret is returned ONCE; callers must store it securely.
    """
    prefix, raw = _make_api_key()
    hashed = _hash_api_key(raw)

    api_key = ApiKey(
        key_id=uuid.uuid4(),
        enterprise_id=admin.enterprise_id,
        name=body.name,
        key_prefix=prefix,
        hashed_key=hashed,
        scopes=body.scopes,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyWithSecretResponse(
        key_id=str(api_key.key_id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=list(api_key.scopes or []),
        revoked=api_key.revoked,
        secret=raw,
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enterprise admin — list own API keys (no secrets)."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.enterprise_id == admin.enterprise_id),
    )
    keys = result.scalars().all()
    return [
        ApiKeyResponse(
            key_id=str(k.key_id),
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=list(k.scopes or []),
            revoked=k.revoked,
        )
        for k in keys
    ]


@router.post("/api-keys/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_api_key(
    key_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enterprise admin — revoke an API key."""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_id == uuid.UUID(key_id),
            ApiKey.enterprise_id == admin.enterprise_id,
        )
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(404, "API key not found")

    key.revoked = True
    await db.commit()
    await db.refresh(key)

    return ApiKeyResponse(
        key_id=str(key.key_id),
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=list(key.scopes or []),
        revoked=key.revoked,
    )

