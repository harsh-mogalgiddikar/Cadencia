"""
api/routes/ui.py — UI router for the A2A Treasury Network hackathon demo.

Serves Jinja2 templates at /ui/* with session cookies for auth state.
Proxies requests to the /v1/* API using httpx.

Routes:
    GET  /ui/login                          — Login page
    POST /ui/login                          — Handle login form
    GET  /ui/configure                      — Agent config form
    POST /ui/configure                      — Submit config + create session
    GET  /ui/negotiate/{session_id}         — Negotiation arena page
    POST /ui/negotiate/{session_id}/start   — Trigger autonomous negotiation
    GET  /ui/negotiate/{session_id}/status  — Proxy status (JSON)
    GET  /ui/negotiate/{session_id}/offers  — Proxy offers (JSON)
    GET  /ui/negotiate/{session_id}/audit   — Proxy audit entries (JSON)
    GET  /ui/settlement/{session_id}        — Settlement page
    POST /ui/settlement/{session_id}/pay    — Trigger x402 payment
    GET  /ui/settlement/{session_id}/transcript — Download transcript JSON
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Request, Form, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

logger = logging.getLogger("a2a_treasury.ui")

router = APIRouter(tags=["ui"])

_template_dir = Path(__file__).resolve().parent.parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(_template_dir))

BASE_URL = os.getenv("INTERNAL_BASE_URL", "http://localhost:8000")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
serializer = URLSafeSerializer(SECRET_KEY, salt="a2a-ui-session")

# ─── Demo Accounts ────────────────────────────────────────────────────────────
DEMO_ACCOUNTS = {
    "buyer": {
        "email": os.getenv("DEMO_BUYER_EMAIL", "buyer@bharattech.com"),
        "password": os.getenv("DEMO_BUYER_PASSWORD", "DemoBuyer2026!"),
        "name": "Bharat Tech Imports Pvt Ltd",
        "role": "buyer",
    },
    "seller": {
        "email": os.getenv("DEMO_SELLER_EMAIL", "seller@delhiexports.com"),
        "password": os.getenv("DEMO_SELLER_PASSWORD", "DemoSeller2026!"),
        "name": "Delhi Exports Pvt Ltd",
        "role": "seller",
    },
}


# ─── Session Cookie Helpers ───────────────────────────────────────────────────
def _set_session(response: Response, data: dict) -> None:
    """Store session data in a signed cookie."""
    token = serializer.dumps(data)
    response.set_cookie(
        key="a2a_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=3600 * 24,
    )


def _get_session(request: Request) -> dict | None:
    """Retrieve session data from signed cookie."""
    cookie = request.cookies.get("a2a_session")
    if not cookie:
        return None
    try:
        return serializer.loads(cookie)
    except Exception:
        return None


def _clear_session(response: Response) -> None:
    """Remove session cookie."""
    response.delete_cookie("a2a_session")


def _auth_headers(session: dict) -> dict:
    """Build authorization header from session JWT."""
    token = session.get("jwt_token", "")
    return {"Authorization": f"Bearer {token}"}


# ─── GET /ui/login ────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page with quick-login cards."""
    session = _get_session(request)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "session_enterprise": session.get("enterprise_name") if session else None,
        "demo_buyer_email": DEMO_ACCOUNTS["buyer"]["email"],
        "demo_buyer_password": DEMO_ACCOUNTS["buyer"]["password"],
        "demo_seller_email": DEMO_ACCOUNTS["seller"]["email"],
        "demo_seller_password": DEMO_ACCOUNTS["seller"]["password"],
    })


# ─── POST /ui/login ──────────────────────────────────────────────────────────
@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    quick_role: str = Form(""),
):
    """Handle login form, call /v1/auth/login, store JWT in session cookie."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{BASE_URL}/v1/auth/login", json={
            "email": email,
            "password": password,
        })

    if resp.status_code != 200:
        logger.warning("Login failed for %s: %s", email, resp.status_code)
        return HTMLResponse(
            content="<html><body>Login failed. <a href='/ui/login'>Try again</a></body></html>",
            status_code=401,
        )

    data = resp.json()
    jwt_token = data["access_token"]

    # Decode JWT to get enterprise_id (without verification — just parse payload)
    import json as _json
    import base64
    try:
        payload_b64 = jwt_token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        jwt_payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        enterprise_id = jwt_payload.get("enterprise_id", "")
        user_id = jwt_payload.get("sub", "")
    except Exception:
        enterprise_id = ""
        user_id = ""

    # Determine role and name
    role = quick_role or "buyer"
    enterprise_name = ""

    # Try to fetch enterprise name
    if enterprise_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                ent_resp = await client.get(
                    f"{BASE_URL}/v1/enterprises/{enterprise_id}",
                    headers={"Authorization": f"Bearer {jwt_token}"},
                )
                if ent_resp.status_code == 200:
                    ent_data = ent_resp.json()
                    enterprise_name = ent_data.get("legal_name", "")
        except Exception:
            pass

    # Determine role from enterprise name if not set
    if not enterprise_name:
        for acct in DEMO_ACCOUNTS.values():
            if acct["email"] == email:
                enterprise_name = acct["name"]
                role = acct["role"]
                break

    # Determine counterparty enterprise_id
    counterparty_enterprise_id = ""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            ents_resp = await client.get(
                f"{BASE_URL}/v1/enterprises/?page=1&page_size=10",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )
            if ents_resp.status_code == 200:
                items = ents_resp.json().get("items", [])
                for item in items:
                    if item["enterprise_id"] != enterprise_id:
                        counterparty_enterprise_id = item["enterprise_id"]
                        break
    except Exception:
        pass

    session_data = {
        "jwt_token": jwt_token,
        "enterprise_id": enterprise_id,
        "enterprise_name": enterprise_name,
        "role": role,
        "counterparty_id": counterparty_enterprise_id,
    }

    response = RedirectResponse(url="/ui/configure", status_code=303)
    _set_session(response, session_data)
    return response


# ─── GET /ui/configure ────────────────────────────────────────────────────────
@router.get("/configure", response_class=HTMLResponse)
async def configure_page(request: Request):
    """Agent configuration form."""
    session = _get_session(request)
    if not session:
        return RedirectResponse(url="/ui/login", status_code=303)

    return templates.TemplateResponse("configure.html", {
        "request": request,
        "session_enterprise": session.get("enterprise_name"),
        "enterprise_name": session.get("enterprise_name", "Unknown"),
        "role": session.get("role", "buyer"),
    })


# ─── POST /ui/configure ──────────────────────────────────────────────────────
@router.post("/configure")
async def configure_submit(
    request: Request,
    reservation: float = Form(103040),
    target: float = Form(84640),
    ceiling: float = Form(96000),
    risk: float = Form(0.12),
    strategy: str = Form("anchor_low"),
    concession: str = Form("decreasing"),
):
    """Submit agent config and create negotiation session."""
    session = _get_session(request)
    if not session:
        return RedirectResponse(url="/ui/login", status_code=303)

    headers = _auth_headers(session)
    enterprise_id = session.get("enterprise_id", "")
    role = session.get("role", "buyer")
    counterparty_id = session.get("counterparty_id", "")

    is_buyer = role == "buyer"

    # Compute DANP parameters from form values
    if is_buyer:
        intrinsic_value = 92000.0
        risk_factor = risk
        negotiation_margin = 0.08
        concession_curve = {"1": 0.06, "2": 0.04, "3": 0.025, "4": 0.015, "5": 0.008}
        budget_ceiling = ceiling
    else:
        intrinsic_value = 87000.0
        risk_factor = risk
        negotiation_margin = 0.05
        concession_curve = {"1": 0.05, "2": 0.035, "3": 0.02, "4": 0.01, "5": 0.005}
        budget_ceiling = None

    async with httpx.AsyncClient(timeout=20) as client:
        # Step 1: Set agent config
        config_resp = await client.post(
            f"{BASE_URL}/v1/enterprises/{enterprise_id}/agent-config",
            headers=headers,
            json={
                "agent_role": role,
                "intrinsic_value": intrinsic_value,
                "risk_factor": risk_factor,
                "negotiation_margin": negotiation_margin,
                "concession_curve": concession_curve,
                "budget_ceiling": budget_ceiling,
                "max_exposure": 100000.0,
                "strategy_default": "balanced",
                "max_rounds": 8,
                "timeout_seconds": 3600,
            },
        )
        if config_resp.status_code >= 400:
            logger.error("Agent config failed: %s %s", config_resp.status_code, config_resp.text)

        # Step 2: Set treasury policy
        await client.post(
            f"{BASE_URL}/v1/enterprises/{enterprise_id}/treasury-policy",
            headers=headers,
            json={
                "buffer_threshold": 0.05 if is_buyer else 0.04,
                "risk_tolerance": "balanced",
                "yield_strategy": "none",
            },
        )

        # Step 3: Create negotiation session
        session_body = {
            "seller_enterprise_id": counterparty_id if is_buyer else enterprise_id,
            "initial_offer_value": 85000.0,
            "milestone_template_id": "tmpl-single-delivery",
            "timeout_seconds": 3600,
            "max_rounds": 8,
        }

        # For buyer: buyer creates session with seller as counterparty
        # For seller: we still create from buyer perspective
        #   (the session API requires admin/buyer to create)
        session_resp = await client.post(
            f"{BASE_URL}/v1/sessions/",
            headers=headers,
            json=session_body,
        )

        if session_resp.status_code >= 400:
            logger.error("Session creation failed: %s %s", session_resp.status_code, session_resp.text)
            return HTMLResponse(
                content="<html><body>Session creation failed. <a href='/ui/configure'>Try again</a></body></html>",
                status_code=400,
            )

        session_data = session_resp.json()
        negotiation_session_id = session_data["session_id"]

    # Update cookie with session_id
    current_session = session.copy()
    current_session["negotiation_session_id"] = negotiation_session_id
    response = RedirectResponse(
        url=f"/ui/negotiate/{negotiation_session_id}",
        status_code=303,
    )
    _set_session(response, current_session)
    return response


# ─── GET /ui/negotiate/{session_id} ───────────────────────────────────────────
@router.get("/negotiate/{session_id}", response_class=HTMLResponse)
async def negotiate_page(request: Request, session_id: str):
    """Negotiation arena page."""
    session = _get_session(request)
    if not session:
        return RedirectResponse(url="/ui/login", status_code=303)

    role = session.get("role", "buyer")
    is_buyer = role == "buyer"

    return templates.TemplateResponse("negotiate.html", {
        "request": request,
        "session_enterprise": session.get("enterprise_name"),
        "session_id": session_id,
        "session_id_short": session_id[:8] + "...",
        "buyer_name": DEMO_ACCOUNTS["buyer"]["name"],
        "seller_name": DEMO_ACCOUNTS["seller"]["name"],
        "buyer_target": "84,640",
        "seller_target": "91,350",
        "max_rounds": 8,
    })


# ─── POST /ui/negotiate/{session_id}/start ────────────────────────────────────
@router.post("/negotiate/{session_id}/start")
async def negotiate_start(request: Request, session_id: str):
    """Start autonomous negotiation by calling POST /v1/sessions/{id}/run."""
    session = _get_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    headers = _auth_headers(session)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/v1/sessions/{session_id}/run",
            headers=headers,
        )
        if resp.status_code in (200, 202):
            return JSONResponse({"started": True})
        else:
            return JSONResponse(
                {"error": "Failed to start", "detail": resp.text},
                status_code=resp.status_code,
            )


# ─── GET /ui/negotiate/{session_id}/status ────────────────────────────────────
@router.get("/negotiate/{session_id}/status")
async def negotiate_status(request: Request, session_id: str):
    """Proxy session status to frontend."""
    session = _get_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    headers = _auth_headers(session)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/v1/sessions/{session_id}/status",
            headers=headers,
        )
        if resp.status_code == 200:
            return JSONResponse(resp.json())
        return JSONResponse({"status": "UNKNOWN"}, status_code=resp.status_code)


# ─── GET /ui/negotiate/{session_id}/offers ────────────────────────────────────
@router.get("/negotiate/{session_id}/offers")
async def negotiate_offers(request: Request, session_id: str):
    """Proxy offers to frontend."""
    session = _get_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    headers = _auth_headers(session)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/v1/sessions/{session_id}/offers",
            headers=headers,
        )
        if resp.status_code == 200:
            return JSONResponse(resp.json())
        return JSONResponse({"offers": []}, status_code=resp.status_code)


# ─── GET /ui/negotiate/{session_id}/audit ─────────────────────────────────────
@router.get("/negotiate/{session_id}/audit")
async def negotiate_audit(request: Request, session_id: str):
    """Fetch audit entries for the session."""
    session = _get_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    headers = _auth_headers(session)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/v1/sessions/{session_id}/transcript",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            entries = [
                {
                    "time": e.get("timestamp", "")[:19].split("T")[-1] if "T" in e.get("timestamp", "") else e.get("timestamp", "")[:8],
                    "action": e.get("action", ""),
                }
                for e in data.get("entries", [])
            ]
            return JSONResponse({"entries": entries[-10:]})  # Last 10
        return JSONResponse({"entries": []})


# ─── GET /ui/settlement/{session_id} ──────────────────────────────────────────
@router.get("/settlement/{session_id}", response_class=HTMLResponse)
async def settlement_page(request: Request, session_id: str):
    """Settlement result page."""
    session = _get_session(request)
    if not session:
        return RedirectResponse(url="/ui/login", status_code=303)

    headers = _auth_headers(session)
    enterprise_id = session.get("enterprise_id", "")

    # Fetch all data in parallel
    async with httpx.AsyncClient(timeout=15) as client:
        # Session status
        status_resp = await client.get(
            f"{BASE_URL}/v1/sessions/{session_id}/status", headers=headers,
        )
        status_data = status_resp.json() if status_resp.status_code == 200 else {}

        # Escrow
        escrow_data = None
        try:
            escrow_resp = await client.get(
                f"{BASE_URL}/v1/escrow/session/{session_id}", headers=headers,
            )
            if escrow_resp.status_code == 200:
                esc = escrow_resp.json()
                contract_ref = esc.get("contract_ref", "")
                is_live = contract_ref and len(contract_ref) == 58
                escrow_data = {
                    "contract_ref": contract_ref or "N/A",
                    "network_id": esc.get("network_id", "algorand-testnet"),
                    "status": esc.get("status", "UNKNOWN"),
                    "mode": "LIVE" if is_live else "SIMULATION",
                    "explorer_url": f"https://lora.algokit.io/testnet/account/{contract_ref}" if is_live else None,
                }
        except Exception:
            pass

        # Delivery (x402 payment)
        delivery_data = None
        try:
            # Check if delivery already exists by calling deliver endpoint
            deliver_resp = await client.post(
                f"{BASE_URL}/v1/deliver/{session_id}", headers=headers,
            )
            if deliver_resp.status_code == 200:
                dlv = deliver_resp.json()
                tx_id = dlv.get("payment_tx_id", "")
                is_live_tx = tx_id and len(tx_id) > 20 and not tx_id.startswith("SIM-")
                delivery_data = {
                    "tx_id": tx_id,
                    "amount_usdc": dlv.get("amount_usdc", 0),
                    "network": dlv.get("network", "algorand-testnet"),
                    "explorer_url": f"https://lora.algokit.io/testnet/transaction/{tx_id}" if is_live_tx else None,
                }
        except Exception:
            pass

        # FX rate
        fx_data = None
        try:
            fx_resp = await client.get(
                f"{BASE_URL}/v1/fx/rate", headers=headers,
            )
            if fx_resp.status_code == 200:
                fx = fx_resp.json()
                fx_data = {
                    "rate": f"{fx.get('sell_rate', 0):.8f}",
                    "spread_bps": fx.get("spread_bps", 25),
                    "source": fx.get("source", "frankfurter"),
                }
        except Exception:
            pass

        # Audit chain verification
        audit_chain = None
        audit_entries = []
        try:
            chain_resp = await client.get(
                f"{BASE_URL}/v1/audit/verify-chain?session_id={session_id}",
                headers=headers,
            )
            if chain_resp.status_code == 200:
                audit_chain = chain_resp.json()

            # Get transcript for entries
            transcript_resp = await client.get(
                f"{BASE_URL}/v1/sessions/{session_id}/transcript",
                headers=headers,
            )
            if transcript_resp.status_code == 200:
                transcript = transcript_resp.json()
                audit_entries = [
                    {
                        "action": e.get("action", ""),
                        "hash": (e.get("this_hash", "")[:12] + "...") if e.get("this_hash") else "",
                    }
                    for e in transcript.get("entries", [])
                ]
        except Exception:
            pass

    # Format values
    agreed_value = status_data.get("final_agreed_value")
    agreed_display = f"{agreed_value:,.0f}" if agreed_value else "—"
    fx_rate_value = float(fx_data["rate"]) if fx_data else 0.01100681
    usdc_amount = f"{agreed_value * fx_rate_value:.2f}" if agreed_value else "—"

    # Determine buyer and seller names
    buyer_name = DEMO_ACCOUNTS["buyer"]["name"]
    seller_name = DEMO_ACCOUNTS["seller"]["name"]

    return templates.TemplateResponse("settlement.html", {
        "request": request,
        "session_enterprise": session.get("enterprise_name"),
        "session_id": session_id,
        "session_id_short": session_id[:8] + "...",
        "buyer_name": buyer_name,
        "seller_name": seller_name,
        "agreed_value": agreed_display,
        "usdc_amount": usdc_amount,
        "rounds": status_data.get("current_round", 0),
        "session_status": status_data.get("status", "UNKNOWN"),
        "escrow": escrow_data,
        "delivery": delivery_data,
        "fx_rate": fx_data,
        "audit_chain": audit_chain,
        "audit_entries": audit_entries,
        "enterprise_id": enterprise_id,
    })


# ─── POST /ui/settlement/{session_id}/pay ─────────────────────────────────────
@router.post("/settlement/{session_id}/pay")
async def settlement_pay(request: Request, session_id: str):
    """Trigger x402 payment for the session."""
    session = _get_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    headers = _auth_headers(session)

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: GET 402 to get payment requirements
        resp_402 = await client.post(
            f"{BASE_URL}/v1/deliver/{session_id}", headers=headers,
        )

        if resp_402.status_code == 200:
            # Already delivered (idempotent)
            data = resp_402.json()
            tx_id = data.get("payment_tx_id", "")
            is_live_tx = tx_id and len(tx_id) > 20 and not tx_id.startswith("SIM-")
            return JSONResponse({
                "tx_id": tx_id,
                "amount_usdc": data.get("amount_usdc"),
                "network": data.get("network"),
                "explorer_url": f"https://lora.algokit.io/testnet/transaction/{tx_id}" if is_live_tx else None,
            })

        if resp_402.status_code != 402:
            return JSONResponse({"error": f"Unexpected status: {resp_402.status_code}"}, status_code=400)

        # Step 2: GET x402 requirements and create signed payment
        payment_reqs = resp_402.json()

        # Use x402 handler to sign payment (x402 protocol: 402 → sign → retry)
        try:
            from core.x402_handler import x402_handler
            x_payment = x402_handler.sign_payment_algorand(
                payment_requirements=payment_reqs,
            )
        except Exception as e:
            logger.error("x402 payment signing failed: %s", e)
            return JSONResponse({"error": f"Payment signing failed: {str(e)}"}, status_code=500)

        # Step 3: Retry with X-PAYMENT header
        resp_200 = await client.post(
            f"{BASE_URL}/v1/deliver/{session_id}",
            headers={**headers, "X-PAYMENT": x_payment},
        )

        if resp_200.status_code == 200:
            data = resp_200.json()
            tx_id = data.get("payment_tx_id", "")
            is_live_tx = tx_id and len(tx_id) > 20 and not tx_id.startswith("SIM-")
            return JSONResponse({
                "tx_id": tx_id,
                "amount_usdc": data.get("amount_usdc"),
                "network": data.get("network"),
                "explorer_url": f"https://lora.algokit.io/testnet/transaction/{tx_id}" if is_live_tx else None,
            })
        else:
            return JSONResponse(
                {"error": f"Payment verification failed: {resp_200.text}"},
                status_code=resp_200.status_code,
            )


# ─── GET /ui/settlement/{session_id}/transcript ──────────────────────────────
@router.get("/settlement/{session_id}/transcript")
async def settlement_transcript(request: Request, session_id: str):
    """Download full transcript as JSON file."""
    session = _get_session(request)
    if not session:
        return RedirectResponse(url="/ui/login", status_code=303)

    headers = _auth_headers(session)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/v1/sessions/{session_id}/transcript",
            headers=headers,
        )
        if resp.status_code == 200:
            return Response(
                content=resp.content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="transcript_{session_id[:8]}.json"',
                },
            )
        return JSONResponse({"error": "Transcript not available"}, status_code=404)
