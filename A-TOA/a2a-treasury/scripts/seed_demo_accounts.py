#!/usr/bin/env python3
"""
scripts/seed_demo_accounts.py — Seed demo buyer + seller accounts for the UI.

Creates two enterprises, verifies emails, activates them, sets agent configs
with the exact DANP parameters from simulate_negotiation.py, and stores
enterprise IDs in Redis for quick lookup.

Usage:
    python scripts/seed_demo_accounts.py

Requires:
    - API running at localhost:8000
    - PostgreSQL + Redis running (via docker-compose)
"""
from __future__ import annotations

import asyncio
import os
import sys

# Load .env from project root
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
_SKIP_DOCKER_VARS = {"DATABASE_URL", "REDIS_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key = _key.strip()
                _val = _val.strip()
                if _key and _key not in os.environ and _key not in _SKIP_DOCKER_VARS:
                    os.environ[_key] = _val

import httpx

# ─── Configuration ──────────────────────────────────────────────────────────
BASE_URL = os.getenv("INTERNAL_BASE_URL", "http://localhost:8000")

BUYER = {
    "legal_name": "Bharat Tech Imports Pvt Ltd",
    "pan": "AABBT1111B",
    "gst": "27AABBT1111B1Z1",
    "authorized_signatory": "Arjun Kapoor",
    "primary_bank_account": "1111222233334444",
    "wallet_address": os.getenv("BUYER_WALLET_ADDRESS", "ALGO_BUYER_DEMO_001"),
    "email": os.getenv("DEMO_BUYER_EMAIL", "buyer@bharattech.com"),
    "password": os.getenv("DEMO_BUYER_PASSWORD", "DemoBuyer2026!"),
}

SELLER = {
    "legal_name": "Delhi Exports Pvt Ltd",
    "pan": "AABBD2222D",
    "gst": "07AABBD2222D1Z2",
    "authorized_signatory": "Priya Singh",
    "primary_bank_account": "5555666677778888",
    "wallet_address": os.getenv("SELLER_WALLET_ADDRESS", "ALGO_SELLER_DEMO_002"),
    "email": os.getenv("DEMO_SELLER_EMAIL", "seller@delhiexports.com"),
    "password": os.getenv("DEMO_SELLER_PASSWORD", "DemoSeller2026!"),
}


def _vp(p: str) -> str:
    """Version prefix."""
    return f"/v1{p}" if p.startswith("/") else f"/v1/{p}"


async def seed():
    """Seed demo accounts."""
    print("=" * 55)
    print("  A2A Treasury Network — Seeding Demo Accounts")
    print("=" * 55)
    print()

    # Health check
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code != 200:
                print(f"✗ API not healthy at {BASE_URL} (status {resp.status_code})")
                sys.exit(1)
            print(f"✓ API healthy at {BASE_URL}")
        except httpx.ConnectError:
            print(f"✗ Cannot connect to API at {BASE_URL}")
            print("  Start with: docker-compose up -d")
            sys.exit(1)

    async with httpx.AsyncClient(timeout=30) as client:
        # ── Step 1: Register Buyer ──────────────────────────────────
        print("\n── Registering enterprises...")
        buyer_resp = await client.post(f"{BASE_URL}{_vp('/enterprises/register')}", json=BUYER)
        if buyer_resp.status_code == 409:
            # Already exists — try to login instead
            print("  Buyer already registered, logging in...")
            login_resp = await client.post(f"{BASE_URL}{_vp('/auth/login')}", json={
                "email": BUYER["email"],
                "password": BUYER["password"],
            })
            if login_resp.status_code != 200:
                print(f"  ✗ Buyer login failed: {login_resp.status_code}")
                print(f"    {login_resp.text}")
                sys.exit(1)
            buyer_token = login_resp.json()["access_token"]

            # Decode JWT to get enterprise_id
            import json as _json, base64
            payload_b64 = buyer_token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            buyer_eid = _json.loads(base64.urlsafe_b64decode(payload_b64)).get("enterprise_id", "")
            print(f"  ✓ Buyer: {buyer_eid}")
        elif buyer_resp.status_code == 201:
            buyer_data = buyer_resp.json()
            buyer_eid = buyer_data["enterprise_id"]
            buyer_vtoken = buyer_data["verification_token"]
            print(f"  ✓ Buyer registered: {buyer_eid}")

            # Verify email
            await client.post(f"{BASE_URL}{_vp(f'/enterprises/{buyer_eid}/verify-email')}", json={
                "verification_token": buyer_vtoken,
            })
            print("  ✓ Buyer email verified")

            # Login
            login_resp = await client.post(f"{BASE_URL}{_vp('/auth/login')}", json={
                "email": BUYER["email"],
                "password": BUYER["password"],
            })
            buyer_token = login_resp.json()["access_token"]

            # Activate
            await client.post(f"{BASE_URL}{_vp(f'/enterprises/{buyer_eid}/activate')}",
                              headers={"Authorization": f"Bearer {buyer_token}"})
            print("  ✓ Buyer enterprise ACTIVE")
        else:
            print(f"  ✗ Buyer registration failed: {buyer_resp.status_code}")
            print(f"    {buyer_resp.text}")
            sys.exit(1)

        # ── Step 2: Register Seller ─────────────────────────────────
        seller_resp = await client.post(f"{BASE_URL}{_vp('/enterprises/register')}", json=SELLER)
        if seller_resp.status_code == 409:
            print("  Seller already registered, logging in...")
            login_resp = await client.post(f"{BASE_URL}{_vp('/auth/login')}", json={
                "email": SELLER["email"],
                "password": SELLER["password"],
            })
            if login_resp.status_code != 200:
                print(f"  ✗ Seller login failed: {login_resp.status_code}")
                sys.exit(1)
            seller_token = login_resp.json()["access_token"]

            import json as _json, base64
            payload_b64 = seller_token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            seller_eid = _json.loads(base64.urlsafe_b64decode(payload_b64)).get("enterprise_id", "")
            print(f"  ✓ Seller: {seller_eid}")
        elif seller_resp.status_code == 201:
            seller_data = seller_resp.json()
            seller_eid = seller_data["enterprise_id"]
            seller_vtoken = seller_data["verification_token"]
            print(f"  ✓ Seller registered: {seller_eid}")

            # Verify email
            await client.post(f"{BASE_URL}{_vp(f'/enterprises/{seller_eid}/verify-email')}", json={
                "verification_token": seller_vtoken,
            })
            print("  ✓ Seller email verified")

            # Need buyer token for activation (admin)
            if 'buyer_token' not in dir():
                login_resp = await client.post(f"{BASE_URL}{_vp('/auth/login')}", json={
                    "email": BUYER["email"],
                    "password": BUYER["password"],
                })
                buyer_token = login_resp.json()["access_token"]

            # Activate (using buyer token — admin)
            await client.post(f"{BASE_URL}{_vp(f'/enterprises/{seller_eid}/activate')}",
                              headers={"Authorization": f"Bearer {buyer_token}"})
            print("  ✓ Seller enterprise ACTIVE")

            # Login as seller
            login_resp = await client.post(f"{BASE_URL}{_vp('/auth/login')}", json={
                "email": SELLER["email"],
                "password": SELLER["password"],
            })
            seller_token = login_resp.json()["access_token"]
        else:
            print(f"  ✗ Seller registration failed: {seller_resp.status_code}")
            print(f"    {seller_resp.text}")
            sys.exit(1)

        # ── Step 3: Configure Agent Params ──────────────────────────
        print("\n── Configuring agents...")

        # Make sure we have buyer_token
        if 'buyer_token' not in dir():
            login_resp = await client.post(f"{BASE_URL}{_vp('/auth/login')}", json={
                "email": BUYER["email"],
                "password": BUYER["password"],
            })
            buyer_token = login_resp.json()["access_token"]

        auth_h = {"Authorization": f"Bearer {buyer_token}"}

        # Buyer agent config (exact params from simulate_negotiation.py)
        await client.post(f"{BASE_URL}{_vp(f'/enterprises/{buyer_eid}/agent-config')}",
                          headers=auth_h, json={
            "agent_role": "buyer",
            "intrinsic_value": 92000.00,
            "risk_factor": 0.12,
            "negotiation_margin": 0.08,
            "concession_curve": {"1": 0.06, "2": 0.04, "3": 0.025, "4": 0.015, "5": 0.008},
            "budget_ceiling": 96000.00,
            "max_exposure": 100000.00,
            "strategy_default": "balanced",
            "max_rounds": 8,
            "timeout_seconds": 3600,
        })
        print("  ✓ Buyer agent: reservation=₹103,040 | target=₹84,640 | ceiling=₹96,000")

        await client.post(f"{BASE_URL}{_vp(f'/enterprises/{buyer_eid}/treasury-policy')}",
                          headers=auth_h, json={
            "buffer_threshold": 0.05,
            "risk_tolerance": "balanced",
            "yield_strategy": "none",
        })

        # Seller agent config
        await client.post(f"{BASE_URL}{_vp(f'/enterprises/{seller_eid}/agent-config')}",
                          headers=auth_h, json={
            "agent_role": "seller",
            "intrinsic_value": 87000.00,
            "risk_factor": 0.06,
            "negotiation_margin": 0.05,
            "concession_curve": {"1": 0.05, "2": 0.035, "3": 0.02, "4": 0.01, "5": 0.005},
            "budget_ceiling": None,
            "max_exposure": 100000.00,
            "strategy_default": "balanced",
            "max_rounds": 8,
            "timeout_seconds": 3600,
        })
        print("  ✓ Seller agent: reservation=₹81,780 | target=₹91,350")

        await client.post(f"{BASE_URL}{_vp(f'/enterprises/{seller_eid}/treasury-policy')}",
                          headers=auth_h, json={
            "buffer_threshold": 0.04,
            "risk_tolerance": "balanced",
            "yield_strategy": "none",
        })

    # ── Step 4: Store in Redis ──────────────────────────────────────
    print("\n── Storing demo IDs in Redis...")
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = aioredis.from_url(redis_url)
        await r.set("demo:buyer:enterprise_id", buyer_eid)
        await r.set("demo:seller:enterprise_id", seller_eid)
        await r.aclose()
        print("  ✓ Redis keys set")
    except Exception as e:
        print(f"  ⚠ Redis store skipped: {e}")

    # ── Done ────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("  ✓ Demo accounts seeded")
    print(f"    Buyer ID:  {buyer_eid}")
    print(f"    Seller ID: {seller_eid}")
    print(f"    Login at:  {BASE_URL}/ui/login")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(seed())
