"""
api/schemas/auth.py — Auth request/response Pydantic models.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterUserRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(..., pattern=r"^(admin|auditor)$")
    enterprise_id: str


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterUserResponse(BaseModel):
    user_id: str
    email: str
    role: str
    enterprise_id: str


class MessageResponse(BaseModel):
    detail: str
