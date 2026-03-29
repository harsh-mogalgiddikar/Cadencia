"""
api/schemas/session.py — Session + action envelope Pydantic models.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class CreateSessionRequest(BaseModel):
    seller_enterprise_id: str
    initial_offer_value: float = Field(..., gt=0)
    milestone_template_id: str = Field("tmpl-single-delivery")
    timeout_seconds: int = Field(3600, ge=60, le=86400)
    max_rounds: int = Field(8, ge=1, le=50)


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    buyer_enterprise_id: str
    seller_enterprise_id: str
    max_rounds: int
    timeout_at: str
    created_at: str


class AgentActionEnvelope(BaseModel):
    """
    Agent action submission envelope. The single schema for all agent actions.
    """
    session_id: str
    agent_role: Literal["buyer", "seller"]
    round: int = Field(..., ge=1)
    action: Literal["counter", "accept", "reject", "timeout_yield"]
    offer_value: Optional[float] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    strategy_tag: Optional[Literal[
        "anchor", "concede", "hold", "deadline_push",
    ]] = None
    rationale: Optional[str] = None
    timestamp: str  # ISO 8601 UTC

    @field_validator("offer_value")
    @classmethod
    def validate_offer_value(cls, v, info):
        action = info.data.get("action")
        if action == "counter" and v is None:
            raise ValueError("offer_value is required when action is 'counter'")
        if action in ("accept", "reject", "timeout_yield") and v is not None:
            raise ValueError(
                f"offer_value must be None when action is '{action}'",
            )
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v):
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise ValueError("timestamp must be valid ISO 8601 format")
        return v


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    current_round: int
    max_rounds: Optional[int] = None
    timeout_at: str
    is_terminal: bool
    outcome: Optional[str] = None
    final_agreed_value: Optional[float] = None
    expected_turn: Optional[Literal["buyer", "seller"]] = None


class ActionResponse(BaseModel):
    session_id: str
    status: str
    current_round: int
    last_action: str
    agent_role: str
    offer_value: Optional[float] = None
    timeout_at: str
    is_terminal: bool


class OfferDetail(BaseModel):
    offer_id: str
    agent_role: str
    value: Optional[float] = None
    action: str
    round: int
    confidence: Optional[float] = None
    strategy_tag: Optional[str] = None
    timestamp: str
    # NOTE: rationale is NEVER included per spec


class OfferListResponse(BaseModel):
    session_id: str
    offers: list[OfferDetail]


class SessionListResponse(BaseModel):
    items: list[SessionStatusResponse]
    total: int
    page: int
