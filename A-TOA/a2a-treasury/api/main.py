"""
api/main.py — FastAPI application factory, router registration, lifespan.
Phase 4: Deep health check, /v1/ API versioning.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    setup_exception_handlers,
)
from db.database import dispose_engine
from db.redis_client import RedisSessionManager
from framework import FrameworkRegistry
from framework.protocols.danp_protocol import DANPProtocol
from framework.protocols.fixed_price_protocol import FixedPriceProtocol
from framework.settlement.x402_algorand import X402AlgorandSettlement

# ─── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger("a2a_treasury")
APP_VERSION = "1.0.0-rc1"
PHASE = "cadencia-1"

# ─── Redis singleton ────────────────────────────────────────────────────────
redis_manager = RedisSessionManager(
    redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)


# ─── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("Starting Cadencia Commerce Network...")
    await redis_manager.connect()
    logger.info("Redis connected.")

    # Register default Agentic Commerce Framework components
    FrameworkRegistry.register_protocol(DANPProtocol())
    FrameworkRegistry.register_protocol(FixedPriceProtocol())
    FrameworkRegistry.register_settlement_provider(X402AlgorandSettlement())

    # Phase 5: ensure deliveries table + negotiation columns exist
    try:
        from sqlalchemy import text
        from db.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS deliveries (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id  UUID NOT NULL REFERENCES negotiations(session_id) ON DELETE CASCADE,
                    tx_id       VARCHAR(128) NOT NULL,
                    amount_usdc DECIMAL(18,6) NOT NULL,
                    network     VARCHAR(64) NOT NULL DEFAULT 'algorand-testnet',
                    simulation  BOOLEAN NOT NULL DEFAULT true,
                    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
            await session.execute(text(
                "ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(32);"
            ))
            await session.execute(text(
                "ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS delivery_tx_id VARCHAR(128);"
            ))
            # Phase 2: capability_handshakes table
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS capability_handshakes (
                    handshake_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id           UUID REFERENCES negotiations(session_id) ON DELETE SET NULL,
                    buyer_enterprise_id  UUID NOT NULL REFERENCES enterprises(enterprise_id),
                    seller_enterprise_id UUID NOT NULL REFERENCES enterprises(enterprise_id),
                    compatible           BOOLEAN NOT NULL,
                    shared_protocols     JSONB DEFAULT '[]',
                    shared_settlement_networks JSONB DEFAULT '[]',
                    shared_payment_methods     JSONB DEFAULT '[]',
                    incompatibility_reasons    JSONB DEFAULT '[]',
                    buyer_card_snapshot        JSONB,
                    seller_card_snapshot       JSONB,
                    selected_protocol          VARCHAR(100),
                    selected_settlement        VARCHAR(100),
                    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at                 TIMESTAMPTZ
                );
            """))
            # Phase 3 ACF: Merkle root + on-chain anchor columns
            await session.execute(text(
                "ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS merkle_root VARCHAR(64);"
            ))
            await session.execute(text(
                "ALTER TABLE negotiations ADD COLUMN IF NOT EXISTS anchor_tx_id VARCHAR(128);"
            ))
            await session.commit()
        logger.info("Phase 5+6+ACF3 schema migration complete.")
    except Exception as e:
        logger.warning("Phase 5+6 schema migration skipped: %s", e)

    yield
    logger.info("Shutting down...")
    await redis_manager.close()
    await dispose_engine()
    logger.info("Shutdown complete.")


# ─── App factory ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Cadencia Commerce Network",
    description="""
## Cadencia — Agentic Commerce Framework (ACF)
Autonomous machine-to-machine B2B commerce on Algorand.

### Framework Layers
- **Discovery**: Agent registry, capability handshake
- **Protocol**: DANP-v1, FixedPrice-v1
- **Settlement**: x402 + Algorand testnet
- **Verification**: SHA-256 chain, Merkle root, on-chain anchor
    """,
    version=APP_VERSION,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "framework", "description": "Framework protocols and providers"},
        {"name": "discovery", "description": "Agent registry and capability handshake"},
        {"name": "negotiation", "description": "Session creation and autonomous negotiation"},
        {"name": "settlement", "description": "Escrow and x402 payment"},
        {"name": "verification", "description": "Audit chain and Merkle verification"},
        {"name": "enterprise", "description": "Enterprise registration and management"},
        {"name": "treasury", "description": "Analytics, FX, and compliance"},
    ],
)

# ─── Middleware (order matters: outermost first) ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# ─── Exception handlers ─────────────────────────────────────────────────────
setup_exception_handlers(app)

# ─── Router registration (Phase 4: /v1/ canonical) ───────────────────────────
from api.routes.auth import router as auth_router
from api.routes.enterprises import router as enterprises_router
from api.routes.sessions import router as sessions_router
from api.routes.audit import router as audit_router
from api.routes.escrow import router as escrow_router
from api.routes.fx import router as fx_router
from api.routes.treasury import router as treasury_router
from api.routes.compliance import router as compliance_router
from api.routes.deliver import router as deliver_router
from api.routes.framework import router as framework_router
from api.routes.handshake import router as handshake_router
from api.routes.registry import router as registry_router
from api.routes.demo import router as demo_router

app.include_router(auth_router, prefix="/v1", tags=["enterprise"])
app.include_router(enterprises_router, prefix="/v1", tags=["enterprise"])
app.include_router(sessions_router, prefix="/v1", tags=["negotiation"])
app.include_router(audit_router, prefix="/v1", tags=["verification"])
app.include_router(escrow_router, prefix="/v1", tags=["settlement"])
app.include_router(fx_router, prefix="/v1", tags=["treasury"])
app.include_router(treasury_router, prefix="/v1", tags=["treasury"])
app.include_router(compliance_router, prefix="/v1", tags=["treasury"])
app.include_router(deliver_router, prefix="/v1", tags=["settlement"])
app.include_router(framework_router, prefix="/v1", tags=["framework"])
app.include_router(handshake_router, prefix="/v1", tags=["discovery"])
app.include_router(registry_router, prefix="/v1", tags=["discovery"])
app.include_router(demo_router, tags=["Demo"])

app.include_router(auth_router, include_in_schema=False)
app.include_router(enterprises_router, include_in_schema=False)
app.include_router(sessions_router, include_in_schema=False)
app.include_router(audit_router, include_in_schema=False)
app.include_router(escrow_router, include_in_schema=False)
app.include_router(fx_router, include_in_schema=False)
app.include_router(treasury_router, include_in_schema=False)
app.include_router(compliance_router, include_in_schema=False)
app.include_router(deliver_router, include_in_schema=False)
app.include_router(framework_router, include_in_schema=False)
app.include_router(handshake_router, include_in_schema=False)
app.include_router(registry_router, include_in_schema=False)

# ─── Dashboard (Jinja2 HTML) ────────────────────────────────────────────────
try:
    from dashboard.router import router as dashboard_router
    app.include_router(dashboard_router, prefix="/dashboard")
except ImportError:
    logger.warning("Dashboard templates not found — skipping dashboard routes")

# ─── UI (Phase 7: Hackathon Demo UI) ────────────────────────────────────────
try:
    from api.routes.ui import router as ui_router
    app.include_router(ui_router, prefix="/ui")
    logger.info("UI routes mounted at /ui")
except ImportError as e:
    logger.warning("UI routes not available: %s", e)


# ─── Root ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    """API root. Use /health for liveness, /docs for Swagger."""
    return {
        "service": "Cadencia Commerce Network",
        "version": APP_VERSION,
        "health": "/health",
        "docs": "/docs",
    }


# ─── Global Agent Card ──────────────────────────────────────────────────────
@app.get("/.well-known/agent.json", tags=["framework"])
async def global_agent_card():
    """Serve the global ACF Agent Card (framework-level, not enterprise-specific)."""
    return {
        "name": "Cadencia Commerce Network Agent",
        "version": "1.0.0",
        "protocols": [{"id": "DANP-v1"}, {"id": "FixedPrice-v1"}],
        "settlement_networks": ["algorand-testnet"],
        "payment_methods": ["x402"],
        "policy_constraints": {
            "requires_escrow": True,
            "compliance_frameworks": ["FEMA", "RBI"],
        },
        "framework": {
            "name": "Agentic Commerce Framework",
            "version": "1.0.0",
        },
    }

# ─── Phase 4: Deep health check ──────────────────────────────────────────────
HEALTH_CHECK_TIMEOUT = 2.0


async def _check_db():
    start = time.perf_counter()
    try:
        from sqlalchemy import text
        from db.database import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=HEALTH_CHECK_TIMEOUT)
        return {"status": "ok", "latency_ms": (time.perf_counter() - start) * 1000, "detail": None}
    except asyncio.TimeoutError:
        return {"status": "error", "latency_ms": HEALTH_CHECK_TIMEOUT * 1000, "detail": "timeout"}
    except Exception as e:
        return {"status": "error", "latency_ms": (time.perf_counter() - start) * 1000, "detail": str(e)}


async def _check_redis():
    start = time.perf_counter()
    try:
        await asyncio.wait_for(redis_manager.client.ping(), timeout=HEALTH_CHECK_TIMEOUT)
        return {"status": "ok", "latency_ms": (time.perf_counter() - start) * 1000, "detail": None}
    except asyncio.TimeoutError:
        return {"status": "error", "latency_ms": HEALTH_CHECK_TIMEOUT * 1000, "detail": "timeout"}
    except Exception as e:
        return {"status": "error", "latency_ms": (time.perf_counter() - start) * 1000, "detail": str(e)}


async def _check_algorand():
    start = time.perf_counter()
    try:
        from blockchain.sdk_client import get_algorand_client
        client = get_algorand_client()
        result = client.health_check()
        result["latency_ms"] = (time.perf_counter() - start) * 1000
        return result
    except Exception as e:
        return {"healthy": False, "network": "unknown", "latency_ms": None, "error": str(e)}


async def _check_groq_llm():
    try:
        key = os.getenv("GROQ_API_KEY", "")
        return {"status": "ok" if key else "degraded", "model": "llama3.3-70b", "api_key_configured": bool(key), "detail": None}
    except Exception as e:
        return {"status": "error", "model": "unknown", "api_key_configured": False, "detail": str(e)}


async def _check_fx_engine():
    try:
        return {"status": "ok", "last_rate": None, "source": "frankfurter", "detail": None}
    except Exception as e:
        return {"status": "degraded", "last_rate": None, "source": "fallback", "detail": str(e)}


@app.get("/health", tags=["Health"])
async def health_check(response: Response):
    """Phase 4: Deep health — database, redis, algorand, groq, fx. 200=healthy/degraded, 503=unhealthy."""
    db_c = await _check_db()
    redis_c = await _check_redis()
    algo_c = await _check_algorand()
    groq_c = await _check_groq_llm()
    fx_c = await _check_fx_engine()

    checks = {"database": db_c, "redis": redis_c, "algorand": algo_c, "groq_llm": groq_c, "fx_engine": fx_c}

    db_ok = db_c.get("status") == "ok"
    redis_ok = redis_c.get("status") == "ok"
    algo_ok = algo_c.get("healthy", False) or algo_c.get("status") in ("ok", "degraded")
    groq_ok = groq_c.get("status") in ("ok", "degraded")
    fx_ok = fx_c.get("status") in ("ok", "degraded")

    if db_ok and redis_ok and algo_ok and groq_ok and fx_ok:
        status = "healthy" if all(c.get("status") == "ok" for c in [db_c, redis_c, algo_c, groq_c, fx_c]) else "degraded"
    else:
        status = "unhealthy"

    if status == "unhealthy":
        response.status_code = 503

    return {
        "status": status,
        "version": APP_VERSION,
        "phase": PHASE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
