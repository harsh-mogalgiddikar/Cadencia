"""
api/schemas/saas.py — B2B SaaS Pydantic models for plans, subscriptions, and API keys.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SubscriptionPlanCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    monthly_price_usd: float = Field(0.0, ge=0)
    max_sessions_per_month: Optional[int] = Field(None, ge=1)
    max_concurrent_sessions: Optional[int] = Field(None, ge=1)
    max_enterprises_per_group: Optional[int] = Field(None, ge=1)
    features: dict[str, Any] | None = None


class SubscriptionPlanResponse(BaseModel):
    plan_id: str
    name: str
    description: Optional[str] = None
    monthly_price_usd: float
    max_sessions_per_month: Optional[int] = None
    max_concurrent_sessions: Optional[int] = None
    max_enterprises_per_group: Optional[int] = None
    features: dict[str, Any] | None = None
    active: bool


class SubscriptionPlanListResponse(BaseModel):
    items: list[SubscriptionPlanResponse]


class SubscriptionCreate(BaseModel):
    plan_id: str
    seat_count: int = Field(1, ge=1)
    current_period_end: datetime


class SubscriptionResponse(BaseModel):
    subscription_id: str
    enterprise_id: str
    plan_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    seat_count: int


class ApiKeyCreate(BaseModel):
    name: str = Field(..., max_length=100)
    scopes: list[str] = Field(default_factory=list)


class ApiKeyResponse(BaseModel):
    key_id: str
    name: str
    key_prefix: str
    scopes: list[str] = Field(default_factory=list)
    revoked: bool


class ApiKeyWithSecretResponse(ApiKeyResponse):
    # Returned only at creation time
    secret: str

