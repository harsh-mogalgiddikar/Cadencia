"""
api/routes/enterprises.py — Enterprise registration, verification, activation,
                             agent config, treasury policy, and agent card.
"""
from __future__ import annotations

import json
import secrets
import uuid
from decimal import Decimal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from a2a_protocol.agent_card import generate_agent_card
from api.dependencies import UserContext, require_admin, require_any_role
from api.schemas.enterprise import (
    AgentConfigRequest,
    AgentConfigResponse,
    EnterpriseDetailResponse,
    EnterpriseListResponse,
    EnterpriseRegisterRequest,
    EnterpriseRegisterResponse,
    EnterpriseStatusResponse,
    TreasuryPolicyRequest,
    TreasuryPolicyResponse,
    VerifyEmailRequest,
)
from db.audit_logger import AuditLogger
from db.database import get_db
from db.models import AgentConfig, Enterprise, TreasuryPolicy, User, Wallet

router = APIRouter(prefix="/enterprises", tags=["Enterprises"])
audit_logger = AuditLogger()

BCRYPT_COST = 12


# ─── POST /enterprises/register ────────────────────────────────────────────
@router.post(
    "/register",
    response_model=EnterpriseRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_enterprise(
    body: EnterpriseRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public — register a new enterprise + admin user."""
    # Check email uniqueness
    existing = await db.execute(
        select(User).where(User.email == body.email),
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(409, "Email already registered")

    enterprise = Enterprise(
        enterprise_id=uuid.uuid4(),
        legal_name=body.legal_name,
        pan=body.pan,
        gst=body.gst,
        authorized_signatory=body.authorized_signatory,
        primary_bank_account=body.primary_bank_account,
        wallet_address=body.wallet_address,
        kyc_status="PENDING",
    )
    db.add(enterprise)
    await db.flush()

    # Create admin user for this enterprise (login-capable)
    pw_bytes = body.password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise HTTPException(400, "Password must be 72 bytes or fewer")
    password_hash = bcrypt.hashpw(
        pw_bytes,
        bcrypt.gensalt(rounds=BCRYPT_COST),
    ).decode("utf-8")

    user = User(
        user_id=uuid.uuid4(),
        enterprise_id=enterprise.enterprise_id,
        email=body.email,
        role="admin",
        password_hash=password_hash,
    )
    db.add(user)
    await db.flush()

    # Optional: auto-activate in dev/demo mode to skip manual KYC
    import os
    auto_activate = os.getenv("AUTO_ACTIVATE_ENTERPRISES", "false").lower() == "true"
    if auto_activate:
        enterprise.kyc_status = "ACTIVE"

    # Simulated verification token (MVP: returned in response)
    verification_token = secrets.token_hex(32)

    # Audit
    await audit_logger.append(
        entity_type="enterprise",
        entity_id=str(enterprise.enterprise_id),
        action="ENTERPRISE_REGISTERED",
        actor_id=str(user.user_id),
        payload={"legal_name": body.legal_name, "email": body.email},
        db_session=db,
    )

    # Commit before returning so verify-email (next request) sees the row
    await db.commit()
    await db.refresh(enterprise)

    return EnterpriseRegisterResponse(
        enterprise_id=str(enterprise.enterprise_id),
        legal_name=enterprise.legal_name,
        kyc_status="PENDING",
        verification_token=verification_token,
    )


# ─── POST /enterprises/{id}/verify-email ───────────────────────────────────
@router.post(
    "/{enterprise_id}/verify-email",
    response_model=EnterpriseStatusResponse,
)
async def verify_email(
    enterprise_id: str,
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public — verify email with token (MVP: any token accepted)."""
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    enterprise = result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(404, "Enterprise not found")

    if enterprise.kyc_status != "PENDING":
        raise HTTPException(409, f"Invalid state transition: {enterprise.kyc_status} → EMAIL_VERIFIED")

    await db.execute(
        update(Enterprise)
        .where(Enterprise.enterprise_id == uuid.UUID(enterprise_id))
        .values(kyc_status="EMAIL_VERIFIED"),
    )
    await db.flush()

    await audit_logger.append(
        entity_type="enterprise",
        entity_id=enterprise_id,
        action="EMAIL_VERIFIED",
        actor_id="system",
        payload={},
        db_session=db,
    )

    return EnterpriseStatusResponse(
        enterprise_id=enterprise_id,
        kyc_status="EMAIL_VERIFIED",
    )


# ─── POST /enterprises/{id}/activate ───────────────────────────────────────
@router.post(
    "/{enterprise_id}/activate",
    response_model=EnterpriseStatusResponse,
)
async def activate_enterprise(
    enterprise_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only — activate enterprise + provision agent card."""
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    enterprise = result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(404, "Enterprise not found")

    if enterprise.kyc_status != "EMAIL_VERIFIED":
        raise HTTPException(
            409,
            f"Invalid state transition: {enterprise.kyc_status} → ACTIVE. "
            f"Must be EMAIL_VERIFIED first.",
        )

    # Generate Agent Card (includes ACF capabilities)
    # Try to derive agent role and budget ceiling from AgentConfig, if present.
    cfg_result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    agent_cfg = cfg_result.scalar_one_or_none()
    agent_role = agent_cfg.agent_role if agent_cfg is not None else "buyer"
    budget_ceiling = (
        float(agent_cfg.budget_ceiling) if getattr(agent_cfg, "budget_ceiling", None) else None
    )

    agent_card = generate_agent_card(
        enterprise_id=enterprise_id,
        legal_name=enterprise.legal_name,
        agent_role=agent_role,
        budget_ceiling=budget_ceiling,
    )
    agent_card_url = f"/enterprises/{enterprise_id}/.well-known/agent.json"

    await db.execute(
        update(Enterprise)
        .where(Enterprise.enterprise_id == uuid.UUID(enterprise_id))
        .values(
            kyc_status="ACTIVE",
            agent_card_url=agent_card_url,
            agent_card_data=agent_card,
        ),
    )

    # Create wallet if not exists
    wallet_check = await db.execute(
        select(Wallet).where(
            Wallet.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    if wallet_check.scalar_one_or_none() is None:
        wallet = Wallet(
            wallet_id=uuid.uuid4(),
            enterprise_id=uuid.UUID(enterprise_id),
            address=enterprise.wallet_address or f"ALGO_{enterprise_id[:16]}",
        )
        db.add(wallet)

    await db.flush()

    await audit_logger.append(
        entity_type="enterprise",
        entity_id=enterprise_id,
        action="ENTERPRISE_ACTIVATED",
        actor_id=admin.user_id,
        payload={"agent_card_url": agent_card_url},
        db_session=db,
    )

    return EnterpriseStatusResponse(
        enterprise_id=enterprise_id,
        kyc_status="ACTIVE",
        agent_card_url=agent_card_url,
    )


# ─── GET /enterprises/ ─────────────────────────────────────────────────────
@router.get("/", response_model=EnterpriseListResponse)
async def list_enterprises(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only — paginated list of enterprises."""
    query = select(Enterprise)
    count_query = select(func.count(Enterprise.enterprise_id))

    if status_filter:
        query = query.where(Enterprise.kyc_status == status_filter)
        count_query = count_query.where(Enterprise.kyc_status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Enterprise.created_at.desc())
        .offset(offset)
        .limit(page_size),
    )
    enterprises = result.scalars().all()

    return EnterpriseListResponse(
        items=[
            EnterpriseDetailResponse(
                enterprise_id=str(e.enterprise_id),
                legal_name=e.legal_name,
                pan=e.pan,
                gst=e.gst,
                kyc_status=e.kyc_status,
                wallet_address=e.wallet_address,
                agent_card_url=e.agent_card_url,
                created_at=e.created_at.isoformat() if e.created_at else "",
            )
            for e in enterprises
        ],
        total=total,
        page=page,
    )


# ─── GET /enterprises/{id} ─────────────────────────────────────────────────
@router.get("/{enterprise_id}", response_model=EnterpriseDetailResponse)
async def get_enterprise(
    enterprise_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Any authenticated user — enterprise detail."""
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    enterprise = result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(404, "Enterprise not found")

    return EnterpriseDetailResponse(
        enterprise_id=str(enterprise.enterprise_id),
        legal_name=enterprise.legal_name,
        pan=enterprise.pan,
        gst=enterprise.gst,
        kyc_status=enterprise.kyc_status,
        wallet_address=enterprise.wallet_address,
        agent_card_url=enterprise.agent_card_url,
        created_at=enterprise.created_at.isoformat() if enterprise.created_at else "",
    )


# ─── POST /enterprises/{id}/agent-config ───────────────────────────────────
@router.post(
    "/{enterprise_id}/agent-config",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_agent_config(
    enterprise_id: str,
    body: AgentConfigRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only — set agent negotiation parameters."""
    # Verify enterprise exists
    ent = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    if ent.scalar_one_or_none() is None:
        raise HTTPException(404, "Enterprise not found")

    # Upsert: delete existing config
    existing = await db.execute(
        select(AgentConfig).where(
            AgentConfig.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    old = existing.scalar_one_or_none()
    if old:
        await db.delete(old)
        await db.flush()

    config = AgentConfig(
        config_id=uuid.uuid4(),
        enterprise_id=uuid.UUID(enterprise_id),
        agent_role=body.agent_role,
        intrinsic_value=Decimal(str(body.intrinsic_value)),
        risk_factor=Decimal(str(body.risk_factor)),
        negotiation_margin=Decimal(str(body.negotiation_margin)),
        concession_curve=body.concession_curve,
        budget_ceiling=Decimal(str(body.budget_ceiling)) if body.budget_ceiling else None,
        max_exposure=Decimal(str(body.max_exposure)),
        strategy_default=body.strategy_default,
        max_rounds=body.max_rounds,
        timeout_seconds=body.timeout_seconds,
    )
    db.add(config)
    await db.flush()

    await audit_logger.append(
        entity_type="enterprise",
        entity_id=enterprise_id,
        action="AGENT_CONFIG_SET",
        actor_id=admin.user_id,
        payload={"agent_role": body.agent_role, "intrinsic_value": body.intrinsic_value},
        db_session=db,
    )

    return AgentConfigResponse(
        config_id=str(config.config_id),
        enterprise_id=str(config.enterprise_id),
        agent_role=config.agent_role,
        intrinsic_value=float(config.intrinsic_value),
        risk_factor=float(config.risk_factor),
        negotiation_margin=float(config.negotiation_margin),
        concession_curve=config.concession_curve,
        budget_ceiling=float(config.budget_ceiling) if config.budget_ceiling else None,
        max_exposure=float(config.max_exposure),
        strategy_default=config.strategy_default,
        max_rounds=config.max_rounds,
        timeout_seconds=config.timeout_seconds,
    )


# ─── GET /enterprises/{id}/agent-config ────────────────────────────────────
@router.get(
    "/{enterprise_id}/agent-config",
    response_model=AgentConfigResponse,
)
async def get_agent_config(
    enterprise_id: str,
    user: UserContext = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Get the current agent configuration for an enterprise. 404 if none."""
    ent = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    if ent.scalar_one_or_none() is None:
        raise HTTPException(404, "Enterprise not found")

    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="No agent configuration found for this enterprise. "
                   "Please create one via POST first.",
        )

    return AgentConfigResponse(
        config_id=str(config.config_id),
        enterprise_id=str(config.enterprise_id),
        agent_role=config.agent_role,
        intrinsic_value=float(config.intrinsic_value),
        risk_factor=float(config.risk_factor),
        negotiation_margin=float(config.negotiation_margin),
        concession_curve=config.concession_curve,
        budget_ceiling=float(config.budget_ceiling) if config.budget_ceiling else None,
        max_exposure=float(config.max_exposure),
        strategy_default=config.strategy_default,
        max_rounds=config.max_rounds,
        timeout_seconds=config.timeout_seconds,
    )


# ─── POST /enterprises/{id}/treasury-policy ────────────────────────────────
@router.post(
    "/{enterprise_id}/treasury-policy",
    response_model=TreasuryPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_treasury_policy(
    enterprise_id: str,
    body: TreasuryPolicyRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only — set treasury policy. Deactivates previous."""
    ent = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    if ent.scalar_one_or_none() is None:
        raise HTTPException(404, "Enterprise not found")

    # Deactivate existing active policies
    await db.execute(
        update(TreasuryPolicy)
        .where(
            TreasuryPolicy.enterprise_id == uuid.UUID(enterprise_id),
            TreasuryPolicy.active == True,
        )
        .values(active=False),
    )

    policy = TreasuryPolicy(
        policy_id=uuid.uuid4(),
        enterprise_id=uuid.UUID(enterprise_id),
        buffer_threshold=Decimal(str(body.buffer_threshold)) if body.buffer_threshold else None,
        risk_tolerance=body.risk_tolerance,
        yield_strategy=body.yield_strategy,
        active=True,
    )
    db.add(policy)
    await db.flush()

    await audit_logger.append(
        entity_type="enterprise",
        entity_id=enterprise_id,
        action="TREASURY_POLICY_SET",
        actor_id=admin.user_id,
        payload={"risk_tolerance": body.risk_tolerance},
        db_session=db,
    )

    return TreasuryPolicyResponse(
        policy_id=str(policy.policy_id),
        enterprise_id=str(policy.enterprise_id),
        active=True,
    )


# ─── Phase 4: Webhook config ────────────────────────────────────────────────
class WebhookConfigRequest(BaseModel):
    webhook_url: str
    webhook_secret: str  # min 32 chars


@router.post("/{enterprise_id}/webhook")
async def set_webhook(
    enterprise_id: str,
    body: WebhookConfigRequest,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 4: Set webhook URL and secret. Admin (own enterprise) only. URL must be https://."""
    if admin.enterprise_id != uuid.UUID(enterprise_id):
        raise HTTPException(403, "Can only set webhook for own enterprise")
    if not body.webhook_url.startswith("https://"):
        raise HTTPException(400, "webhook_url must be https://")
    if len(body.webhook_secret) < 32:
        raise HTTPException(400, "webhook_secret must be at least 32 characters")
    result = await db.execute(select(Enterprise).where(Enterprise.enterprise_id == uuid.UUID(enterprise_id)))
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "Enterprise not found")
    ent.webhook_url = body.webhook_url
    ent.webhook_secret = body.webhook_secret
    await db.commit()
    return {"webhook_url": body.webhook_url, "configured": True}


@router.delete("/{enterprise_id}/webhook")
async def delete_webhook(
    enterprise_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.enterprise_id != uuid.UUID(enterprise_id):
        raise HTTPException(403, "Can only delete webhook for own enterprise")
    result = await db.execute(select(Enterprise).where(Enterprise.enterprise_id == uuid.UUID(enterprise_id)))
    ent = result.scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "Enterprise not found")
    ent.webhook_url = None
    ent.webhook_secret = None
    await db.commit()
    return {"webhook_url": None, "configured": False}


@router.get("/{enterprise_id}/webhook/test")
async def test_webhook(
    enterprise_id: str,
    admin: UserContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Phase 4: Send test event to configured webhook."""
    if admin.enterprise_id != uuid.UUID(enterprise_id):
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Enterprise).where(Enterprise.enterprise_id == uuid.UUID(enterprise_id)))
    ent = result.scalar_one_or_none()
    if not ent or not getattr(ent, "webhook_url", None):
        return {"sent": False, "status_code": None, "error": "No webhook configured"}
    from core.webhook_notifier import webhook_notifier
    await webhook_notifier.notify(
        enterprise_id,
        "SESSION_AGREED",
        {"test": True, "message": "Phase 4 webhook test"},
        db,
    )
    return {"sent": True, "status_code": 200, "error": None}


# ─── GET /enterprises/{id}/.well-known/agent.json ──────────────────────────
@router.get("/{enterprise_id}/.well-known/agent.json")
async def get_agent_card(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public — serve A2A Agent Card. Returns 404 if not ACTIVE."""
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.enterprise_id == uuid.UUID(enterprise_id),
        ),
    )
    enterprise = result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(404, "Enterprise not found")

    if enterprise.kyc_status != "ACTIVE":
        raise HTTPException(404, "Agent card not available — enterprise not ACTIVE")

    if enterprise.agent_card_data is None:
        raise HTTPException(404, "Agent card not generated")

    return enterprise.agent_card_data
