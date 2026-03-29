"""
api/dependencies.py — JWT authentication + RBAC guards.

All role enforcement happens HERE — never only on the route decorator.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "changeme")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_EXPIRE_HOURS = int(os.getenv("JWT_ACCESS_EXPIRE_HOURS", "24"))

bearer_scheme = HTTPBearer()


@dataclass
class UserContext:
    """Decoded JWT context for the current request."""
    user_id: str
    enterprise_id: str
    role: str


def create_access_token(
    user_id: str,
    enterprise_id: str,
    role: str,
) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "enterprise_id": enterprise_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_ACCESS_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserContext:
    """FastAPI dependency: decode Bearer token → UserContext."""
    payload = decode_access_token(credentials.credentials)
    return UserContext(
        user_id=payload["sub"],
        enterprise_id=payload["enterprise_id"],
        role=payload["role"],
    )


async def require_admin(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """FastAPI dependency: requires admin role. Raises 403 if not admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_any_role(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """FastAPI dependency: any authenticated user."""
    return user
