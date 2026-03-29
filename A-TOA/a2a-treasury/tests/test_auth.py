"""
tests/test_auth.py — Tests for JWT authentication and RBAC.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from api.dependencies import (
    UserContext,
    create_access_token,
    decode_access_token,
)

# Ensure test env
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_testing_only_64chars_0000000000000000000000"
os.environ["JWT_ALGORITHM"] = "HS256"


class TestJWTCreation:
    def test_create_valid_token(self):
        token = create_access_token(
            user_id="user-123",
            enterprise_id="ent-456",
            role="admin",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_claims(self):
        token = create_access_token(
            user_id="user-123",
            enterprise_id="ent-456",
            role="admin",
        )
        payload = decode_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["enterprise_id"] == "ent-456"
        assert payload["role"] == "admin"


class TestJWTDecoding:
    def test_expired_token_rejected(self):
        from fastapi import HTTPException
        # Create an already-expired token
        payload = {
            "sub": "user-123",
            "enterprise_id": "ent-456",
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(
            payload,
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401

    def test_invalid_token_rejected(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("not.a.valid.token")
        assert exc_info.value.status_code == 401


class TestRBACContext:
    def test_admin_context(self):
        token = create_access_token("user-1", "ent-1", "admin")
        payload = decode_access_token(token)
        ctx = UserContext(
            user_id=payload["sub"],
            enterprise_id=payload["enterprise_id"],
            role=payload["role"],
        )
        assert ctx.role == "admin"

    def test_auditor_context(self):
        token = create_access_token("user-2", "ent-2", "auditor")
        payload = decode_access_token(token)
        ctx = UserContext(
            user_id=payload["sub"],
            enterprise_id=payload["enterprise_id"],
            role=payload["role"],
        )
        assert ctx.role == "auditor"
