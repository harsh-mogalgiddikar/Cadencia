"""
Demo orchestration endpoint.
Runs the full A2A Treasury flow end-to-end and streams progress via SSE.

Flow:
  Phase 1  — Seed buyer + seller enterprises (or reuse existing demo accounts)
  Phase 2  — Register both agents in discovery registry
  Phase 3  — Run capability handshake
  Phase 4  — Create negotiation session
  Phase 5  — Run autonomous negotiation (DANP-v1)
  Phase 6  — Poll until terminal state (AGREED)
  Phase 7  — Deploy Algorand escrow smart contract
  Phase 8  — Fund escrow (USDC transfer)
  Phase 9  — Execute x402 payment delivery
  Phase 10 — Release escrow to seller
  Phase 11 — Compute + anchor Merkle root on Algorand
  Phase 12 — Return all tx hashes + Lora Explorer links
"""

import asyncio
import json
import logging
import os
import uuid
from decimal import Decimal

import bcrypt
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from typing import AsyncGenerator

from db.models import Enterprise, User, AgentConfig, TreasuryPolicy, Wallet
from db.database import get_session_factory

logger = logging.getLogger("a2a_treasury")

router = APIRouter(prefix="/v1/demo", tags=["Demo"])

# ── Demo account constants ─────────────────────────────────────────────────
DEMO_BUYER_EMAIL = "demo-buyer@a2atreasury.internal"
DEMO_SELLER_EMAIL = "demo-seller@a2atreasury.internal"
DEMO_PASSWORD = "DemoPass@2026"

DEMO_BUYER_CONFIG = {
    "agent_role":         "buyer",
    "intrinsic_value":    90000.0,
    "risk_factor":        0.12,
    "negotiation_margin": 0.08,
    "concession_curve":   {"1": 0.05, "2": 0.04, "3": 0.03, "4": 0.02, "5": 0.01},
    "budget_ceiling":     95000.0,
    "max_exposure":       100000.0,
    "strategy_default":   "concede",
    "max_rounds":         5,
    "timeout_seconds":    120,
}

DEMO_SELLER_CONFIG = {
    "agent_role":         "seller",
    "intrinsic_value":    85000.0,
    "risk_factor":        0.10,
    "negotiation_margin": 0.10,
    "concession_curve":   {"1": 0.04, "2": 0.03, "3": 0.03, "4": 0.02, "5": 0.01},
    "budget_ceiling":     None,
    "max_exposure":       200000.0,
    "strategy_default":   "anchor",
    "max_rounds":         5,
    "timeout_seconds":    120,
}


def make_event(phase: int, status: str, label: str, detail: str = "",
               data: dict = None) -> str:
    """
    Serialize a single SSE event as a JSON string.

    status: "running" | "done" | "error"
    """
    payload = {
        "phase":  phase,
        "status": status,
        "label":  label,
        "detail": detail,
        "data":   data or {},
    }
    return f"data: {json.dumps(payload)}\n\n"


async def get_or_create_demo_enterprise(
    db,
    email: str,
    legal_name: str,
    pan: str,
    gst: str,
    wallet_address: str,
    agent_config: dict,
) -> tuple:
    """
    Returns (enterprise_id, user_id).
    Creates enterprise + user + agent config + treasury policy if they don't exist.
    Resets agent config on every demo run to ensure clean state.
    """
    # Check if enterprise already exists (by email-based user lookup)
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Create enterprise
        enterprise = Enterprise(
            enterprise_id=uuid.uuid4(),
            legal_name=legal_name,
            pan=pan,
            gst=gst,
            wallet_address=wallet_address,
            authorized_signatory=legal_name,
            primary_bank_account="DEMO-BANK-001",
            kyc_status="ACTIVE",   # pre-activated for demo
        )
        db.add(enterprise)
        await db.flush()

        # Create admin user
        pw_hash = bcrypt.hashpw(
            DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=10)
        ).decode("utf-8")
        user = User(
            user_id=uuid.uuid4(),
            enterprise_id=enterprise.enterprise_id,
            email=email,
            role="admin",
            password_hash=pw_hash,
        )
        db.add(user)
        await db.flush()
    else:
        # Load existing enterprise
        ent_result = await db.execute(
            select(Enterprise).where(Enterprise.enterprise_id == user.enterprise_id)
        )
        enterprise = ent_result.scalar_one_or_none()

    # Always upsert agent config for clean demo state
    cfg_result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.enterprise_id == enterprise.enterprise_id
        )
    )
    existing_cfg = cfg_result.scalar_one_or_none()
    if existing_cfg:
        for k, v in agent_config.items():
            setattr(existing_cfg, k, v)
    else:
        new_cfg = AgentConfig(
            config_id=uuid.uuid4(),
            enterprise_id=enterprise.enterprise_id,
            **agent_config,
        )
        db.add(new_cfg)

    await db.flush()

    # ── Ensure TreasuryPolicy exists (required by session creation) ──────
    tp_result = await db.execute(
        select(TreasuryPolicy).where(
            TreasuryPolicy.enterprise_id == enterprise.enterprise_id,
            TreasuryPolicy.active == True,
        )
    )
    existing_policy = tp_result.scalar_one_or_none()
    if existing_policy is None:
        policy = TreasuryPolicy(
            policy_id=uuid.uuid4(),
            enterprise_id=enterprise.enterprise_id,
            buffer_threshold=Decimal("0.05"),
            risk_tolerance="medium",
            yield_strategy="none",
            active=True,
        )
        db.add(policy)
        await db.flush()

    # ── Ensure Wallet row exists (required by escrow manager) ────────────
    if wallet_address:
        wl_result = await db.execute(
            select(Wallet).where(
                Wallet.enterprise_id == enterprise.enterprise_id
            )
        )
        existing_wallet = wl_result.scalar_one_or_none()
        if existing_wallet is None:
            wallet = Wallet(
                wallet_id=uuid.uuid4(),
                enterprise_id=enterprise.enterprise_id,
                address=wallet_address,
                usdc_balance=Decimal("100000.000000"),
                network_id="algorand-testnet",
            )
            db.add(wallet)
        else:
            existing_wallet.address = wallet_address
        await db.flush()

    await db.commit()
    await db.refresh(enterprise)
    return str(enterprise.enterprise_id), str(user.user_id)


async def run_demo_flow(
    buyer_wallet: str,
    seller_wallet: str,
    live_mode: bool,
) -> AsyncGenerator[str, None]:
    """
    Full demo orchestration generator.
    Yields SSE events for each phase.
    """
    import httpx

    BASE = f"http://localhost:{os.getenv('PORT', '8000')}"
    results = {}  # accumulates all tx hashes / IDs for final summary
    simulation = os.getenv("ALGORAND_SIMULATION", "true").lower() == "true"

    # ── PHASE 0: Pre-flight wallet balance check (LIVE mode only) ────────
    if not simulation:
        yield make_event(0, "running", "Checking Algorand wallet balance",
                         "Verifying buyer wallet has sufficient ALGOs…")
        try:
            from blockchain.algo_client import AlgorandClient
            algo_client = AlgorandClient()
            buyer_addr = buyer_wallet or os.getenv("BUYER_WALLET_ADDRESS", "")
            if algo_client.sdk_available and buyer_addr:
                account_info = await algo_client.get_account_info(buyer_addr)
                balance_micro = account_info.get("amount", 0)
                balance_algo = balance_micro / 1_000_000

                MIN_BALANCE_ALGO = 0.5  # minimum needed for demo

                if balance_algo < MIN_BALANCE_ALGO:
                    yield make_event(0, "error",
                                     f"Insufficient balance: {balance_algo:.4f} ALGO",
                                     f"Buyer wallet {buyer_addr[:12]}… needs at least "
                                     f"{MIN_BALANCE_ALGO} ALGO. "
                                     f"Fund it at: https://bank.testnet.algorand.network/")
                    return

                yield make_event(0, "done",
                                 f"Wallet funded: {balance_algo:.4f} ALGO available",
                                 f"Buyer: {buyer_addr[:12]}…{buyer_addr[-6:]}",
                                 {
                                     "buyer_address": buyer_addr,
                                     "balance_algo":  balance_algo,
                                     "mode":          "LIVE",
                                 })
            else:
                yield make_event(0, "running",
                                 "Balance check skipped",
                                 "SDK unavailable or no buyer address")
        except Exception as e:
            # Non-fatal — warn but proceed
            yield make_event(0, "running",
                             "Balance check skipped",
                             f"Could not verify wallet: {e}")

        await asyncio.sleep(0.3)

    # ── PHASE 1: Seed demo enterprises ──────────────────────────────────────
    yield make_event(1, "running", "Seeding demo enterprises",
                     "Creating buyer and seller accounts with pre-configured agent policies…")

    try:
        factory = get_session_factory()
        async with factory() as db:
            buyer_id, _ = await get_or_create_demo_enterprise(
                db=db,
                email=DEMO_BUYER_EMAIL,
                legal_name="Bharat Textiles Pvt. Ltd.",
                pan="AAACB1234F",
                gst="27AAACB1234F1Z5",
                wallet_address=buyer_wallet or os.getenv("BUYER_WALLET_ADDRESS", ""),
                agent_config=DEMO_BUYER_CONFIG,
            )
            seller_id, _ = await get_or_create_demo_enterprise(
                db=db,
                email=DEMO_SELLER_EMAIL,
                legal_name="Gujarat Fabrics Ltd.",
                pan="AABCG5678K",
                gst="24AABCG5678K1Z3",
                wallet_address=seller_wallet or os.getenv("SELLER_WALLET_ADDRESS", ""),
                agent_config=DEMO_SELLER_CONFIG,
            )

        results["buyer_enterprise_id"] = buyer_id
        results["seller_enterprise_id"] = seller_id
        yield make_event(1, "done", "Demo enterprises ready",
                         f"Buyer: Bharat Textiles (…{buyer_id[-8:]}) | "
                         f"Seller: Gujarat Fabrics (…{seller_id[-8:]})",
                         {"buyer_id": buyer_id, "seller_id": seller_id})
    except Exception as e:
        logger.exception("Phase 1 error: %s", e)
        yield make_event(1, "error", "Enterprise seeding failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── Login as buyer to get JWT ────────────────────────────────────────────
    token = None
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
            login_res = await client.post("/v1/auth/login", json={
                "email": DEMO_BUYER_EMAIL, "password": DEMO_PASSWORD
            })
            login_res.raise_for_status()
            token = login_res.json()["access_token"]
    except Exception as e:
        logger.exception("Demo login failed: %s", e)
        yield make_event(1, "error", "Demo login failed", str(e))
        return

    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}

    # ── PHASE 2: Register agents in discovery registry ───────────────────────
    yield make_event(2, "running", "Registering agents in discovery registry",
                     "Publishing buyer and seller capability cards to Redis registry…")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
            # Buyer agent registration
            await client.post(
                "/v1/agents/register",
                json={
                    "service_tags": ["cotton", "textiles", "B2B-trade"],
                    "description":  "Bharat Textiles autonomous buyer agent",
                    "availability": "active",
                },
                headers=headers,
            )

            # Login as seller + register seller agent
            seller_login = await client.post("/v1/auth/login", json={
                "email": DEMO_SELLER_EMAIL, "password": DEMO_PASSWORD
            })
            seller_token = seller_login.json()["access_token"]
            seller_headers = {"Authorization": f"Bearer {seller_token}",
                              "Content-Type": "application/json"}
            await client.post(
                "/v1/agents/register",
                json={
                    "service_tags": ["cotton", "textiles", "B2B-trade"],
                    "description":  "Gujarat Fabrics autonomous seller agent",
                    "availability": "active",
                },
                headers=seller_headers,
            )

        yield make_event(2, "done", "Agents registered in discovery registry",
                         "Both agents discoverable via DANP-v1 + x402-algorand-testnet",
                         {"protocol": "DANP-v1", "settlement": "x402-algorand-testnet"})
    except Exception as e:
        logger.exception("Phase 2 error: %s", e)
        yield make_event(2, "error", "Agent registration failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 3: Capability handshake ────────────────────────────────────────
    yield make_event(3, "running", "Running capability handshake",
                     "Verifying shared protocols, settlement networks, and payment methods…")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
            hs_res = await client.post(
                "/v1/handshake/",
                json={
                    "buyer_enterprise_id":  buyer_id,
                    "seller_enterprise_id": seller_id,
                },
                headers=headers,
            )
            # 200 = compatible, 409 = incompatible
            if hs_res.status_code == 409:
                yield make_event(3, "error", "Handshake failed — incompatible",
                                 hs_res.json().get("message", ""))
                return

            hs_data = hs_res.json()
            results["handshake_id"] = hs_data.get("handshake_id")

        yield make_event(3, "done", "Handshake successful — agents compatible",
                         f"Protocol: {hs_data.get('selected_protocol')} | "
                         f"Settlement: {hs_data.get('selected_settlement')}",
                         {
                             "handshake_id":        hs_data.get("handshake_id"),
                             "selected_protocol":   hs_data.get("selected_protocol"),
                             "selected_settlement": hs_data.get("selected_settlement"),
                         })
    except Exception as e:
        logger.exception("Phase 3 error: %s", e)
        yield make_event(3, "error", "Handshake error", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 4: Create negotiation session ──────────────────────────────────
    yield make_event(4, "running", "Creating negotiation session",
                     "Initialising DANP-v1 finite state machine…")

    session_id = None
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
            sess_res = await client.post(
                "/v1/sessions/",
                json={
                    "seller_enterprise_id": seller_id,
                    "initial_offer_value":  float(85000),
                    "max_rounds":           int(5),
                    "timeout_seconds":      int(120),
                },
                headers=headers,
            )

            if sess_res.status_code not in (200, 201):
                error_body = sess_res.text
                logger.error(
                    "Phase 4: Session creation failed (%s): %s",
                    sess_res.status_code, error_body,
                )
                yield make_event(4, "error",
                                 f"Session creation failed ({sess_res.status_code})",
                                 error_body)
                return

            sess_data = sess_res.json()
            session_id = (
                sess_data.get("session_id") or
                sess_data.get("id") or
                sess_data.get("negotiation_id")
            )
            if not session_id:
                yield make_event(4, "error", "Session created but ID missing",
                                 f"Response was: {sess_data}")
                return

            results["session_id"] = session_id

        yield make_event(4, "done", "Session created",
                         f"Session ID: …{session_id[-12:]} | "
                         f"Opening offer: ₹85,000",
                         {"session_id": session_id, "initial_offer": 85000})
    except Exception as e:
        logger.exception("Phase 4 error: %s", e)
        yield make_event(4, "error", "Session creation failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 5: Run autonomous negotiation ──────────────────────────────────
    yield make_event(5, "running", "Launching autonomous negotiation",
                     "AI agents negotiating without human input — DANP-v1 FSM active…")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
            run_res = await client.post(
                f"/v1/sessions/{session_id}/run",
                headers=headers,
            )

            if run_res.status_code not in (200, 201, 202):
                error_body = run_res.text
                logger.error(
                    "Phase 5: Negotiation run failed (%s): %s",
                    run_res.status_code, error_body,
                )
                yield make_event(5, "error",
                                 f"Negotiation run failed ({run_res.status_code})",
                                 error_body)
                return

        yield make_event(5, "done", "Negotiation engine started",
                         "Autonomous rounds in progress — polling for terminal state…",
                         {"session_id": session_id})
    except Exception as e:
        logger.exception("Phase 5 error: %s", e)
        yield make_event(5, "error", "Negotiation launch failed", str(e))
        return

    # ── PHASE 6: Poll for AGREED terminal state ───────────────────────────────
    yield make_event(6, "running", "Negotiation in progress",
                     "Waiting for agents to reach agreement…")

    agreed_value = None
    final_status = None
    max_polls = 60   # 60 × 2s = 120s timeout
    polls = 0
    TERMINAL = {"AGREED", "WALKAWAY", "TIMEOUT", "ROUND_LIMIT",
                "STALLED", "POLICY_BREACH"}

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=10) as client:
            while polls < max_polls:
                await asyncio.sleep(2)
                polls += 1

                status_res = await client.get(
                    f"/v1/sessions/{session_id}/status",
                    headers=headers,
                )
                status_data = status_res.json()
                current = status_data.get("status", "")
                round_num = status_data.get("current_round", 0)
                max_rounds = status_data.get("max_rounds", 5)

                # Stream round-by-round progress
                yield make_event(6, "running",
                                 f"Negotiation in progress — Round {round_num}/{max_rounds}",
                                 f"Status: {current}",
                                 {"current_round": round_num,
                                  "status": current})

                if current in TERMINAL:
                    final_status = current
                    agreed_value = status_data.get("final_agreed_value")
                    break

        if final_status != "AGREED":
            yield make_event(6, "error",
                             f"Negotiation ended: {final_status}",
                             "Demo accounts may need re-configuration. "
                             "Try running again.")
            return

        results["agreed_value"] = agreed_value
        yield make_event(6, "done",
                         f"AGREED at ₹{agreed_value:,.0f}" if agreed_value else "AGREED",
                         "Both agents accepted the price. "
                         "Triggering escrow deployment…",
                         {"final_agreed_value": agreed_value,
                          "status": "AGREED"})
    except Exception as e:
        logger.exception("Phase 6 error: %s", e)
        yield make_event(6, "error", "Polling error", str(e))
        return

    await asyncio.sleep(0.5)

    # ── PHASE 7: Get escrow contract (auto-deployed on AGREED) ───────────────
    yield make_event(7, "running", "Fetching Algorand escrow contract",
                     "Smart contract auto-deployed on AGREED state — retrieving details…")

    escrow_id = None
    escrow_data = {}
    last_escrow_response = ""
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
            for attempt in range(15):   # retry up to 15 × 3s = 45s
                await asyncio.sleep(3)
                yield make_event(7, "running",
                                 f"Waiting for escrow deployment… ({attempt + 1}/15)",
                                 "Algorand contract deploying after AGREED state")
                escrow_res = await client.get(
                    f"/v1/escrow/session/{session_id}",
                    headers=headers,
                )
                last_escrow_response = escrow_res.text
                if escrow_res.status_code == 200:
                    escrow_data = escrow_res.json()
                    escrow_id = escrow_data.get("escrow_id")
                    if escrow_id:
                        break

        if not escrow_id:
            yield make_event(7, "error",
                             "Escrow contract not found after 45s",
                             f"Session {session_id} reached AGREED but no escrow "
                             f"was deployed. Check backend logs for escrow_manager "
                             f"errors. Last response: {last_escrow_response}")
            return

        results["escrow_id"] = escrow_id
        results["contract_ref"] = escrow_data.get("contract_ref")
        results["app_id"] = escrow_data.get("app_id")

        yield make_event(7, "done", "Algorand escrow contract deployed",
                         f"Contract ref: {escrow_data.get('contract_ref')} | "
                         f"App ID: {escrow_data.get('app_id')}",
                         {
                             "escrow_id":    escrow_id,
                             "contract_ref": escrow_data.get("contract_ref"),
                             "app_id":       escrow_data.get("app_id"),
                             "network":      escrow_data.get("network_id"),
                         })
    except Exception as e:
        logger.exception("Phase 7 error: %s", e)
        yield make_event(7, "error", "Escrow fetch failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 8: Fund escrow ──────────────────────────────────────────────────
    yield make_event(8, "running", "Funding escrow contract",
                     "Buyer agent transferring USDC to Algorand smart contract…")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
            fund_res = await client.post(
                f"/v1/escrow/{escrow_id}/fund",
                headers=headers,
            )
            fund_data = fund_res.json()
            fund_tx_id = fund_data.get("tx_id") or fund_data.get("fund_tx_id")
            results["fund_tx_id"] = fund_tx_id

        explorer_fund = (
            f"https://lora.algokit.io/testnet/transaction/{fund_tx_id}"
            if fund_tx_id and not str(fund_tx_id).startswith("SIM")
            else None
        )
        results["explorer_fund"] = explorer_fund

        yield make_event(8, "done", "Escrow funded",
                         f"USDC locked in contract | TX: {fund_tx_id}",
                         {
                             "fund_tx_id":   fund_tx_id,
                             "explorer_url": explorer_fund,
                             "simulated":    str(fund_tx_id).startswith("SIM")
                                             if fund_tx_id else True,
                         })
    except Exception as e:
        logger.exception("Phase 8 error: %s", e)
        yield make_event(8, "error", "Escrow funding failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 9: x402 payment delivery ───────────────────────────────────────
    yield make_event(9, "running", "Executing x402 payment",
                     "HTTP 402 challenge issued → buyer agent signing Algorand PaymentTxn…")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
            deliver_res = await client.post(
                f"/v1/deliver/{session_id}",
                headers=headers,
            )

            if deliver_res.status_code == 402:
                # Second call — with X-PAYMENT token
                challenge = deliver_res.json()
                pay_token = (challenge.get("payment_token") or
                             challenge.get("x402_token") or
                             f"DEMO-X402-{session_id[:8]}")
                final_res = await client.post(
                    f"/v1/deliver/{session_id}",
                    headers={**headers, "X-PAYMENT": pay_token},
                )
                deliver_data = final_res.json()
            else:
                deliver_data = deliver_res.json()

            payment_tx_id = (
                deliver_data.get("payment_tx_id") or
                deliver_data.get("tx_id")
            )
            results["payment_tx_id"] = payment_tx_id

        explorer_pay = (
            f"https://lora.algokit.io/testnet/transaction/{payment_tx_id}"
            if payment_tx_id and not str(payment_tx_id).startswith("SIM")
            else None
        )
        results["explorer_payment"] = explorer_pay

        yield make_event(9, "done", "x402 payment confirmed",
                         f"Payment TX: {payment_tx_id} | "
                         f"x402 verified: {deliver_data.get('x402_verified', False)}",
                         {
                             "payment_tx_id": payment_tx_id,
                             "x402_verified":  deliver_data.get("x402_verified"),
                             "explorer_url":   explorer_pay,
                             "simulated":      str(payment_tx_id).startswith("SIM")
                                               if payment_tx_id else True,
                         })
    except Exception as e:
        logger.exception("Phase 9 error: %s", e)
        yield make_event(9, "error", "x402 payment failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 10: Release escrow to seller ───────────────────────────────────
    yield make_event(10, "running", "Releasing escrow to seller",
                     "Platform releasing USDC from smart contract to seller wallet…")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
            release_res = await client.post(
                f"/v1/escrow/{escrow_id}/release",
                json={"milestone": "milestone-1"},
                headers=headers,
            )
            release_data = release_res.json()
            release_tx_id = (
                release_data.get("tx_id") or
                release_data.get("release_tx_id")
            )
            results["release_tx_id"] = release_tx_id

        explorer_release = (
            f"https://lora.algokit.io/testnet/transaction/{release_tx_id}"
            if release_tx_id and not str(release_tx_id).startswith("SIM")
            else None
        )
        results["explorer_release"] = explorer_release

        yield make_event(10, "done", "Escrow released — seller paid",
                         f"Release TX: {release_tx_id}",
                         {
                             "release_tx_id": release_tx_id,
                             "explorer_url":  explorer_release,
                             "simulated":     str(release_tx_id).startswith("SIM")
                                              if release_tx_id else True,
                         })
    except Exception as e:
        logger.exception("Phase 10 error: %s", e)
        yield make_event(10, "error", "Escrow release failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 11: Anchor Merkle root on Algorand ─────────────────────────────
    yield make_event(11, "running", "Anchoring audit trail on Algorand",
                     "Computing SHA-256 Merkle root from all session events → "
                     "writing to Algorand as transaction note…")

    merkle_data = {}
    leaf_count = 0
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
            for attempt in range(5):
                await asyncio.sleep(3)
                merkle_res = await client.get(
                    f"/v1/audit/{session_id}/merkle",
                    headers=headers,
                )
                merkle_data = merkle_res.json()
                if merkle_data.get("merkle_root") and \
                   merkle_data.get("anchor_tx_id"):
                    break

        merkle_root = merkle_data.get("merkle_root")
        anchor_tx_id = merkle_data.get("anchor_tx_id")
        leaf_count = merkle_data.get("leaf_count", 0)
        results["merkle_root"] = merkle_root
        results["anchor_tx_id"] = anchor_tx_id

        explorer_anchor = (
            f"https://lora.algokit.io/testnet/transaction/{anchor_tx_id}"
            if anchor_tx_id and not str(anchor_tx_id).startswith("SIM")
            else None
        )
        results["explorer_anchor"] = explorer_anchor

        yield make_event(11, "done",
                         "Audit trail anchored on Algorand",
                         f"Merkle root: {str(merkle_root)[:16]}… | "
                         f"{leaf_count} events | Anchor TX: {anchor_tx_id}",
                         {
                             "merkle_root":  merkle_root,
                             "leaf_count":   leaf_count,
                             "anchor_tx_id": anchor_tx_id,
                             "explorer_url": explorer_anchor,
                             "on_chain":     merkle_data.get("anchored_on_chain"),
                         })
    except Exception as e:
        logger.exception("Phase 11 error: %s", e)
        yield make_event(11, "error", "Merkle anchor failed", str(e))
        return

    await asyncio.sleep(0.3)

    # ── PHASE 12: Final summary ───────────────────────────────────────────────
    is_live = not (
        str(results.get("fund_tx_id", "SIM")).startswith("SIM")
    )

    yield make_event(12, "done",
                     "Demo complete — full flow executed on Algorand",
                     f"Negotiated ₹{results.get('agreed_value', 0):,.0f} → "
                     f"Escrow deployed → Funded → x402 paid → Released → "
                     f"Audit anchored {'LIVE on Algorand testnet' if is_live else '(simulation mode)'}",
                     {
                         "summary": {
                             "session_id":       results.get("session_id"),
                             "agreed_value_inr": results.get("agreed_value"),
                             "escrow": {
                                 "escrow_id":    results.get("escrow_id"),
                                 "contract_ref": results.get("contract_ref"),
                                 "app_id":       results.get("app_id"),
                             },
                             "transactions": {
                                 "fund_tx_id":    results.get("fund_tx_id"),
                                 "payment_tx_id": results.get("payment_tx_id"),
                                 "release_tx_id": results.get("release_tx_id"),
                                 "anchor_tx_id":  results.get("anchor_tx_id"),
                             },
                             "explorer_links": {
                                 "fund":    results.get("explorer_fund"),
                                 "payment": results.get("explorer_payment"),
                                 "release": results.get("explorer_release"),
                                 "anchor":  results.get("explorer_anchor"),
                             },
                             "audit": {
                                 "merkle_root": results.get("merkle_root"),
                                 "leaf_count":  leaf_count,
                                 "on_chain":    is_live,
                             },
                             "mode": "LIVE" if is_live else "SIMULATION",
                         }
                     })


@router.get(
    "/run",
    summary="Run full A2A demo flow (SSE stream)",
    description=(
        "Executes the complete A2A Treasury flow end-to-end and streams "
        "real-time progress events via Server-Sent Events. "
        "Each event is a JSON object with phase, status, label, detail, "
        "and data fields."
    ),
)
async def run_demo(
    buyer_wallet:  str = "",
    seller_wallet: str = "",
    live_mode:     bool = False,
):
    return StreamingResponse(
        run_demo_flow(
            buyer_wallet=buyer_wallet or os.getenv("DEMO_BUYER_WALLET", ""),
            seller_wallet=seller_wallet or os.getenv("DEMO_SELLER_WALLET", ""),
            live_mode=live_mode,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.get("/mode")
async def get_demo_mode():
    """Returns whether demo is running in LIVE or SIMULATION mode."""
    simulation = os.getenv("ALGORAND_SIMULATION", "true").lower() == "true"
    anchor = os.getenv("ANCHOR_ENABLED", "false").lower() == "true"
    x402_sim = os.getenv("X402_SIMULATION_MODE", "true").lower() == "true"

    is_live = not simulation and not x402_sim and anchor

    return {
        "mode": "LIVE" if is_live else "SIMULATION",
        "is_live": is_live,
        "algorand_simulation": simulation,
        "anchor_enabled": anchor,
        "x402_simulation": x402_sim,
        "algod_address": os.getenv(
            "ALGORAND_ALGOD_ADDRESS",
            "https://testnet-api.algonode.cloud",
        ),
    }
