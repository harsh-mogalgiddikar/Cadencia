"""
api/schemas/enterprise.py — Enterprise Pydantic request/response models.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class EnterpriseRegisterRequest(BaseModel):
    legal_name: str = Field(..., max_length=255)
    pan: Optional[str] = Field(None, max_length=10)
    gst: Optional[str] = Field(None, max_length=15)
    authorized_signatory: Optional[str] = Field(None, max_length=255)
    primary_bank_account: Optional[str] = Field(None, max_length=50)
    wallet_address: Optional[str] = Field(None, max_length=128)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class EnterpriseRegisterResponse(BaseModel):
    enterprise_id: str
    legal_name: str
    kyc_status: str
    verification_token: Optional[str] = None  # MVP: returned in response


class VerifyEmailRequest(BaseModel):
    verification_token: str


class EnterpriseStatusResponse(BaseModel):
    enterprise_id: str
    kyc_status: str
    agent_card_url: Optional[str] = None


class EnterpriseDetailResponse(BaseModel):
    enterprise_id: str
    legal_name: str
    pan: Optional[str] = None
    gst: Optional[str] = None
    kyc_status: str
    wallet_address: Optional[str] = None
    agent_card_url: Optional[str] = None
    created_at: str


class EnterpriseListResponse(BaseModel):
    items: list[EnterpriseDetailResponse]
    total: int
    page: int


class AgentConfigRequest(BaseModel):
    agent_role: str = Field(..., pattern=r"^(buyer|seller|both)$")
    intrinsic_value: float = Field(..., gt=0)
    risk_factor: float = Field(..., ge=0, le=1)
    negotiation_margin: float = Field(0.08, ge=0, le=1)
    concession_curve: dict = Field(...)
    budget_ceiling: Optional[float] = None
    max_exposure: float = Field(100000.0, gt=0)
    strategy_default: str = Field("balanced", max_length=50)
    max_rounds: int = Field(8, ge=1, le=50)
    timeout_seconds: int = Field(3600, ge=60, le=86400)


class AgentConfigResponse(BaseModel):
    config_id: str
    enterprise_id: str
    agent_role: str
    intrinsic_value: float
    risk_factor: float
    negotiation_margin: float
    concession_curve: dict
    budget_ceiling: Optional[float] = None
    max_exposure: float
    strategy_default: str
    max_rounds: int
    timeout_seconds: int


class TreasuryPolicyRequest(BaseModel):
    buffer_threshold: Optional[float] = None
    risk_tolerance: Optional[str] = Field(None, pattern=r"^(conservative|balanced|aggressive)$")
    yield_strategy: str = Field("none", max_length=50)


class TreasuryPolicyResponse(BaseModel):
    policy_id: str
    enterprise_id: str
    active: bool
