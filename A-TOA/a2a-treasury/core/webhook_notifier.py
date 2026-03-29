"""
core/webhook_notifier.py — Phase 4: Fire-and-forget webhook notifications.

RULE 22: Webhooks NEVER block the main transaction flow.
RULE 23: Payloads NEVER contain private keys, mnemonics, JWT, or full wallet addresses.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.audit_logger import AuditLogger
from db.models import Enterprise

logger = logging.getLogger("a2a_treasury.webhooks")
audit_logger = AuditLogger()

EVENTS = [
    "SESSION_AGREED",
    "SESSION_WALKAWAY",
    "SESSION_TIMEOUT",
    "SESSION_POLICY_BREACH",
    "ESCROW_DEPLOYED",
    "ESCROW_FUNDED",
    "ESCROW_RELEASED",
    "ESCROW_REFUNDED",
    "GUARDRAIL_BLOCKED",
    "COMPLIANCE_BLOCKED",
]


class WebhookNotifier:
    """Fire-and-forget webhook POST with HMAC-SHA256 signature."""

    async def notify(
        self,
        enterprise_id: str,
        event: str,
        payload: dict,
        db_session: AsyncSession,
    ) -> None:
        """
        POST notification to enterprise.webhook_url. Never raises.
        Headers: X-A2A-Signature: sha256={hex}, X-A2A-Event: event.
        Timeout 5s, no retries. Log WEBHOOK_SENT to audit.
        """
        try:
            result = await db_session.execute(
                select(Enterprise).where(Enterprise.enterprise_id == uuid.UUID(str(enterprise_id)))
            )
            ent = result.scalar_one_or_none()
            if not ent or not getattr(ent, "webhook_url", None):
                return
            webhook_url = ent.webhook_url
            webhook_secret = getattr(ent, "webhook_secret", None) or ""
            from datetime import datetime, timezone
            body = {
                "event": event,
                "enterprise_id": str(enterprise_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
            body_bytes = json.dumps(body, default=str).encode()
            sig = hmac.new(
                webhook_secret.encode() if webhook_secret else b"",
                body_bytes,
                hashlib.sha256,
            ).hexdigest()
            import aiohttp
            headers = {
                "X-A2A-Signature": f"sha256={sig}",
                "Content-Type": "application/json",
                "X-A2A-Event": event,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    status_code = resp.status
            await audit_logger.append(
                entity_type="enterprise",
                entity_id=enterprise_id,
                action="WEBHOOK_SENT",
                actor_id="system",
                payload={
                    "event": event,
                    "url": webhook_url[:50] + "..." if len(webhook_url) > 50 else webhook_url,
                    "status_code": status_code,
                    "success": status_code < 400,
                },
                db_session=db_session,
            )
        except Exception as e:
            logger.warning("Webhook notify failed for %s event %s: %s", enterprise_id[:8], event, e)


webhook_notifier = WebhookNotifier()
