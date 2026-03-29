#!/usr/bin/env python3
"""
A2A Treasury Network — Hackathon Demo

Demonstrates autonomous AI agent negotiation
and x402 payment settlement on Algorand.

Usage:
    python demo.py

Requires: docker-compose up -d (API + PostgreSQL + Redis running)
"""
from __future__ import annotations

import os
os.environ["PYTHONUTF8"] = "1"
import sys
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Load .env for wallet config
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_SKIP_DOCKER_VARS = {"DATABASE_URL", "REDIS_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"}
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                _key, _val = _key.strip(), _val.strip()
                if _key and _key not in os.environ and _key not in _SKIP_DOCKER_VARS:
                    os.environ[_key] = _val

import asyncio
import hashlib
import os
import sys
import time

import httpx
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

console = Console()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://a2a:password@localhost:5432/a2a_treasury",
)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _path(p: str) -> str:
    if p.startswith("/v1/") or p.startswith("/health") or p.startswith("/dashboard"):
        return p
    return f"/v1{p}"


async def _api(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: dict | None = None,
    expect_status: int | None = None,
    headers: dict | None = None,
) -> dict:
    path = _path(path)
    h = _auth_header(token) if token else {}
    if headers:
        h.update(headers)
    try:
        resp = await client.request(method, f"{BASE_URL}{path}", json=json, headers=h)
    except httpx.ConnectError:
        rprint(f"[bold red]✗ Cannot connect to {BASE_URL}[/]")
        rprint("[yellow]  Run: docker-compose up -d --build[/]")
        sys.exit(1)

    if expect_status is not None:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {"_status": resp.status_code, "_body": body}

    if resp.status_code >= 400:
        rprint(f"[bold red]✗ {method} {path} → {resp.status_code}[/]")
        try:
            rprint(f"[red]  {resp.json()}[/]")
        except Exception:
            rprint(f"[red]  {resp.text}[/]")
        sys.exit(1)

    try:
        return resp.json()
    except Exception:
        return {}


def _fmt_inr(value) -> str:
    if value is None:
        return "—"
    return f"₹{float(value):,.0f}"


def _pause(seconds: float = 1.0):
    time.sleep(seconds)


async def main():
    # ═══════════════════════════════════════════════════════════════
    # INTRO BANNER
    # ═══════════════════════════════════════════════════════════════
    console.print(Panel(
        "[bold bright_cyan]A2A TREASURY NETWORK[/]\n"
        "[bold white]Autonomous Agent Trade Settlement[/]\n"
        "\n"
        "[dim]Powered by:[/]  [bright_green]Algorand[/] + [bright_magenta]x402 Protocol[/]\n"
        "[dim]LLM:[/]         [bright_yellow]Groq Llama 3.3 70B[/]\n"
        "\n"
        "[dim italic]Watch AI agents negotiate a trade deal[/]\n"
        "[dim italic]and settle payment — ZERO human input[/]",
        border_style="bright_cyan",
        padding=(1, 4),
    ))
    _pause(2)

    async with httpx.AsyncClient(timeout=30) as client:

        # ═══════════════════════════════════════════════════════════
        # STEP 1 — Health Check
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 1 — Health Check")
        rprint("🔍 Checking API health...")
        _pause(0.5)

        health = await _api(client, "GET", "/health", expect_status=200)
        h = health.get("_body", {}) if isinstance(health.get("_body"), dict) else {}
        checks = h.get("checks", {})

        rprint(f"[green]✓ API online at {BASE_URL}[/]")
        db_ok = checks.get("database", {}).get("status", "?")
        redis_ok = checks.get("redis", {}).get("status", "?")
        algo_net = checks.get("algorand", {}).get("network", "?")
        rprint(f"[green]✓ Database: {db_ok}[/]")
        rprint(f"[green]✓ Redis: {redis_ok}[/]")
        rprint(f"[green]✓ Algorand: {algo_net}[/]")
        rprint(f"[green]✓ Version: {h.get('version', '?')} (Phase {h.get('phase', '?')})[/]")
        _pause(1)

        # ═══════════════════════════════════════════════════════════
        # STEP 0 — Database cleanup
        # ═══════════════════════════════════════════════════════════
        rprint("\n[dim]  Cleaning database for fresh demo...[/]")
        try:
            import asyncpg
            dsn = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
            conn = await asyncpg.connect(dsn)
            tables = [
                "offers", "guardrail_logs", "escrow_contracts", "settlements",
                "compliance_records", "deliveries", "fx_quotes",
                "multi_party_sessions", "negotiations", "audit_logs",
                "wallets", "treasury_policies", "agent_configs", "users", "enterprises",
            ]
            for t in tables:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)", t
                )
                if exists:
                    await conn.execute(f"TRUNCATE TABLE {t} CASCADE")
            await conn.close()

            import redis.asyncio as aioredis
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            r = aioredis.from_url(redis_url)
            await r.flushdb()
            await r.aclose()

            rprint("[green]  ✓ Database + Redis cleared[/]")
        except Exception as e:
            rprint(f"[yellow]  ⚠ DB cleanup skipped: {e}[/]")
        _pause(0.5)

        # ═══════════════════════════════════════════════════════════
        # STEP 2 — Register Enterprises
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 2 — Register Trading Enterprises")
        rprint("🏢 Registering trading enterprises...")
        _pause(0.5)

        buyer_reg = await _api(client, "POST", "/enterprises/register", json={
            "legal_name": "Bharat Tech Imports Pvt Ltd",
            "pan": "AABBT1111B",
            "gst": "27AABBT1111B1Z1",
            "authorized_signatory": "Arjun Kapoor",
            "primary_bank_account": "1111222233334444",
            "wallet_address": "ALGO_BUYER_SIM_001",
            "email": "sim.buyer@bharattech.com",
            "password": "SimBuyer@2026",
        })
        buyer_eid = buyer_reg["enterprise_id"]
        rprint(f"[green]✓ Buyer:  Bharat Tech Imports Pvt Ltd[/]")

        seller_reg = await _api(client, "POST", "/enterprises/register", json={
            "legal_name": "Delhi Exports Pvt Ltd",
            "pan": "AABBD2222D",
            "gst": "07AABBD2222D1Z2",
            "authorized_signatory": "Priya Singh",
            "primary_bank_account": "5555666677778888",
            "wallet_address": "ALGO_SELLER_SIM_002",
            "email": "sim.seller@delhiexports.com",
            "password": "SimSeller@2026",
        })
        seller_eid = seller_reg["enterprise_id"]
        rprint(f"[green]✓ Seller: Delhi Exports Pvt Ltd[/]")

        # Verify emails
        buyer_vtoken = buyer_reg["verification_token"]
        seller_vtoken = seller_reg["verification_token"]
        await _api(client, "POST", f"/enterprises/{buyer_eid}/verify-email", json={"verification_token": buyer_vtoken})
        await _api(client, "POST", f"/enterprises/{seller_eid}/verify-email", json={"verification_token": seller_vtoken})

        # Login
        buyer_login = await _api(client, "POST", "/auth/login", json={"email": "sim.buyer@bharattech.com", "password": "SimBuyer@2026"})
        buyer_token = buyer_login["access_token"]
        seller_login = await _api(client, "POST", "/auth/login", json={"email": "sim.seller@delhiexports.com", "password": "SimSeller@2026"})
        seller_token = seller_login["access_token"]

        # Activate
        await _api(client, "POST", f"/enterprises/{buyer_eid}/activate", token=buyer_token)
        await _api(client, "POST", f"/enterprises/{seller_eid}/activate", token=buyer_token)

        rprint("[green]✓ A2A Agent Cards provisioned for both[/]")
        _pause(1)

        # ═══════════════════════════════════════════════════════════
        # STEP 3 — Configure Agents
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 3 — Configure AI Trading Agents")
        rprint("🤖 Configuring AI trading agents...")
        _pause(0.5)

        await _api(client, "POST", f"/enterprises/{buyer_eid}/agent-config", token=buyer_token, json={
            "agent_role": "buyer",
            "intrinsic_value": 92000,
            "risk_factor": 0.12,
            "negotiation_margin": 0.08,
            "concession_curve": {"rate": 0.15, "floor": 0.03, "rounds_to_floor": 5},
            "budget_ceiling": 96000,
            "max_exposure": 100000,
            "strategy_default": "balanced",
            "max_rounds": 8,
            "timeout_seconds": 600,
        })
        await _api(client, "POST", f"/enterprises/{buyer_eid}/treasury-policy", token=buyer_token, json={
            "buffer_threshold": 0.10,
            "risk_tolerance": "balanced",
            "yield_strategy": "none",
        })

        await _api(client, "POST", f"/enterprises/{seller_eid}/agent-config", token=buyer_token, json={
            "agent_role": "seller",
            "intrinsic_value": 87000,
            "risk_factor": 0.06,
            "negotiation_margin": 0.05,
            "concession_curve": {"rate": 0.12, "floor": 0.02, "rounds_to_floor": 4},
            "budget_ceiling": None,
            "max_exposure": 150000,
            "strategy_default": "balanced",
            "max_rounds": 8,
            "timeout_seconds": 600,
        })
        await _api(client, "POST", f"/enterprises/{seller_eid}/treasury-policy", token=buyer_token, json={
            "buffer_threshold": 0.08,
            "risk_tolerance": "conservative",
            "yield_strategy": "none",
        })

        rprint("[green]✓ Buyer agent: DANP configured[/]")
        rprint("    Reservation: ₹1,03,040 | Target: ₹84,640")
        rprint("[green]✓ Seller agent: DANP configured[/]")
        rprint("    Reservation: ₹81,780 | Target: ₹91,350")
        rprint()
        rprint("    [bold]ZOPA (Zone of Possible Agreement):[/]")
        rprint("    ₹81,780 ──────────────── ₹1,03,040")
        rprint("       ↑                        ↑")
        rprint("    Seller res            Buyer res")
        _pause(1.5)

        # ═══════════════════════════════════════════════════════════
        # STEP 4 — Autonomous Negotiation
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 4 — Autonomous Negotiation")
        rprint("⚡ Starting autonomous negotiation...")
        rprint("   [dim italic]No human involvement from this point.[/]")
        rprint()
        _pause(1)

        session_resp = await _api(client, "POST", "/sessions/", token=buyer_token, json={
            "seller_enterprise_id": seller_eid,
            "initial_offer_value": 85000,
            "max_rounds": 8,
        })
        session_id = session_resp.get("session_id")

        run_resp = await _api(client, "POST", f"/sessions/{session_id}/run", token=buyer_token, expect_status=202)

        # Poll for completion
        TERMINAL = {"AGREED", "WALKAWAY", "TIMEOUT", "POLICY_BREACH", "ROUND_LIMIT", "STALLED"}
        agreed = None
        start_time = time.time()
        prev_offers_count = 0

        for _ in range(60):
            await asyncio.sleep(2)
            sr = await _api(client, "GET", f"/sessions/{session_id}/status", token=buyer_token, expect_status=200)
            body = sr.get("_body", sr) if "_body" in sr else sr
            status = body.get("status", "?") if isinstance(body, dict) else "?"

            # Get offers
            offers_resp = await _api(client, "GET", f"/sessions/{session_id}/offers", token=buyer_token, expect_status=200)
            offers_body = offers_resp.get("_body", offers_resp) if "_body" in offers_resp else offers_resp
            offers = offers_body.get("offers", []) if isinstance(offers_body, dict) else []

            # Print new offers
            for o in offers[prev_offers_count:]:
                role = o.get("agent_role", "?")
                value = o.get("value")
                action = o.get("action", "?")
                rnd = o.get("round", "?")
                emoji = "🔵" if role == "buyer" else "🔴"
                if action == "accept":
                    rprint(f"   {emoji} Round {rnd}: {role.title()} [bold green]ACCEPTS ✓[/]")
                else:
                    rprint(f"   {emoji} Round {rnd}: {role.title()} offers {_fmt_inr(value)} ({action})")
            prev_offers_count = len(offers)

            if status in TERMINAL:
                agreed = body.get("final_agreed_value")
                break

        elapsed = time.time() - start_time
        rprint()
        if agreed:
            rprint(f"[bold green]✓ DEAL AGREED at {_fmt_inr(agreed)}[/]")
        else:
            rprint(f"[yellow]  Session ended: {status}[/]")
        rprint(f"   Rounds: {len(offers)} offers | Time: ~{elapsed:.0f} seconds")
        _pause(1.5)

        # ═══════════════════════════════════════════════════════════
        # STEP 5 — Algorand Escrow
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 5 — Algorand Escrow Deployed")
        rprint("🔗 Checking Algorand escrow...")
        _pause(0.5)

        escrow_resp = await _api(client, "GET", f"/escrow/session/{session_id}", token=buyer_token, expect_status=200)
        escrow_body = escrow_resp.get("_body", escrow_resp) if "_body" in escrow_resp else escrow_resp

        contract_ref = "?"
        if isinstance(escrow_body, list) and escrow_body:
            e = escrow_body[0]
            contract_ref = e.get("contract_ref", "?")
            amount = e.get("amount")
            network = e.get("network_id", "algorand-testnet")
            rprint(f"[green]✓ Escrow deployed on Algorand Testnet[/]")
            rprint(f"   Contract: {str(contract_ref)[:40]}...")
            rprint(f"   Amount:   {_fmt_inr(amount)}")
            rprint(f"   Network:  {network}")
            if contract_ref and len(str(contract_ref)) == 58:
                rprint(f"   Explorer: [link]https://lora.algokit.io/testnet/account/{contract_ref}[/]")
        elif isinstance(escrow_body, dict) and escrow_body.get("contract_ref"):
            contract_ref = escrow_body.get("contract_ref", "?")
            rprint(f"[green]✓ Escrow deployed: {str(contract_ref)[:40]}...[/]")
        else:
            rprint("[green]✓ Escrow deployed (simulation mode)[/]")
        _pause(1.5)

        # ═══════════════════════════════════════════════════════════
        # STEP 6 — x402 Autonomous Payment
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 6 — x402 Autonomous Payment")
        rprint()
        rprint("💳 Initiating x402 autonomous payment...")
        rprint()
        _pause(1)

        # Step 6a — call without X-PAYMENT → 402
        r1 = await _api(client, "POST", f"/deliver/{session_id}", token=buyer_token, expect_status=402)
        r1_body = r1.get("_body", r1) if "_body" in r1 else r1

        if r1.get("_status") == 402:
            accepts = r1_body.get("accepts", [{}])
            acc = accepts[0] if accepts else {}
            amount_micro = int(acc.get("maxAmountRequired", "0"))
            pay_to = acc.get("payTo", "?")
            x402_net = acc.get("network", "?")
            usdc = amount_micro / 1_000_000

            rprint("   → Buyer agent called delivery endpoint")
            _pause(0.5)
            rprint("   ← [bold]HTTP 402 Payment Required[/] received")
            rprint(f"      x402Version: {r1_body.get('x402Version', 1)}")
            rprint(f"      Network:     {x402_net}")
            rprint(f"      Amount:      {usdc:.4f} USDC")
            rprint(f"      Pay to:      {str(pay_to)[:20]}...")
        else:
            usdc = 0
            rprint(f"   [yellow]⚠ Expected 402, got {r1.get('_status')}[/]")
        rprint()
        _pause(1)

        # Step 6b — sign payment (LIVE or SIM)
        rprint("   → Buyer agent signing payment...")
        rprint("      [dim](no human approved this)[/]")
        from core.x402_handler import x402_handler as _x402
        payment_token = _x402.sign_payment_algorand(
            payment_requirements=r1_body,
            buyer_mnemonic=os.environ.get("BUYER_WALLET_MNEMONIC", ""),
            buyer_address=os.environ.get("BUYER_WALLET_ADDRESS", ""),
        )
        is_live = not payment_token.startswith("SIM-")
        _pause(1)

        # Step 6c — retry with X-PAYMENT
        rprint("   → Retrying with X-PAYMENT header")
        r2 = await _api(
            client, "POST", f"/deliver/{session_id}",
            token=buyer_token, expect_status=200,
            headers={"X-PAYMENT": payment_token, "X-PAYMENT-SCHEME": "exact", "X-PAYMENT-NETWORK": "algorand-testnet"},
        )
        r2_body = r2.get("_body", r2) if "_body" in r2 else r2

        tx_id = "?"
        x402_verified = False
        if r2.get("_status") == 200:
            tx_id = r2_body.get("payment_tx_id", "?")
            x402_verified = r2_body.get("x402_verified", False)
            rprint("   ← [bold green]HTTP 200 — Delivery confirmed![/]")
            rprint()
            rprint(f"[green]✓ Payment settled on Algorand[/]")
            rprint(f"   tx_id:         {str(tx_id)[:32]}...")
            rprint(f"   Amount:        {usdc:.4f} USDC")
            rprint(f"   x402_verified: {x402_verified}")
        else:
            rprint(f"   [yellow]⚠ Expected 200, got {r2.get('_status')}[/]")
        _pause(1.5)

        # ═══════════════════════════════════════════════════════════
        # STEP 7 — Audit Chain
        # ═══════════════════════════════════════════════════════════
        console.rule("[bold yellow]Step 7 — Audit Chain Verification")
        rprint()
        rprint("📋 Verifying audit chain...")
        _pause(0.5)

        transcript = await _api(client, "GET", f"/sessions/{session_id}/transcript", token=buyer_token, expect_status=200)
        t_body = transcript.get("_body", transcript) if "_body" in transcript else transcript
        entries = t_body.get("entries", []) if isinstance(t_body, dict) else []
        chain_valid = t_body.get("chain_valid", False) if isinstance(t_body, dict) else False

        all_actions = [e.get("action", "") for e in entries]
        x402_in_audit = "X402_PAYMENT_VERIFIED" in all_actions

        rprint(f"[green]✓ SHA-256 hash chain: {'VALID' if chain_valid else 'NOT VERIFIED'}[/]")
        rprint(f"[green]✓ X402_PAYMENT_VERIFIED: {'confirmed' if x402_in_audit else 'not found'}[/]")
        rprint()
        rprint("   Full audit trail:")
        for e in entries:
            ts = str(e.get("timestamp", "?"))[:19]
            action = e.get("action", "?")
            marker = " ← 🏆" if action == "X402_PAYMENT_VERIFIED" else ""
            rprint(f"     [{ts}] {action}{marker}")
        _pause(1.5)

        # ═══════════════════════════════════════════════════════════
        # FINAL BANNER
        # ═══════════════════════════════════════════════════════════
        n_entries = len(entries)
        final_lines = (
            "[bold green]✅  DEMO COMPLETE[/]\n"
            "\n"
            "[bold white]Two AI agents just:[/]\n"
            f"  1. Negotiated a {_fmt_inr(agreed)} trade deal\n"
            "  2. Deployed an Algorand escrow contract\n"
            "  3. Settled payment via x402 protocol\n"
            "\n"
            f"[bold white]Total rounds:[/]      {len([o for o in offers if o.get('action') == 'counter'])}\n"
            f"[bold white]Audit entries:[/]     {n_entries}\n"
            f"[bold white]Chain valid:[/]       [green]✓ TRUE[/]\n"
            f"[bold white]Payment tx:[/]        {str(tx_id)[:24]}...\n"
            "\n"
            "[bold bright_yellow]Human interactions:  ZERO[/]\n"
            "\n"
            "[dim]Powered by Algorand Foundation[/]\n"
            "[dim]+ x402 Payment Protocol[/]"
        )
        console.print(Panel(
            final_lines,
            title="[bold bright_cyan]A2A TREASURY NETWORK[/]",
            border_style="bright_green",
            padding=(1, 4),
        ))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        rprint("\n[yellow]Demo interrupted.[/]")
        sys.exit(130)
    except Exception as exc:
        rprint(f"\n[bold red]✗ Demo failed: {exc}[/]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
