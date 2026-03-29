"""
api/middleware.py — Request logging, correlation ID, global error handler,
                    and prompt injection defense.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("a2a_treasury")

# ─── Prompt injection blacklist ─────────────────────────────────────────────
_INJECTION_PATTERNS = re.compile(
    r"(?i)"
    r"(ignore\s+previous\s+instructions?"
    r"|system\s*:"
    r"|\[INST\]"
    r"|<\|im_start\|>"
    r"|<\|endoftext\|>"
    r"|###\s*system"
    r"|SYSTEM\s+PROMPT"
    r"|assistant\s*:"
    r"|forget\s+all\s+previous"
    r"|disregard)"
)


def sanitize_rationale(text: str | None) -> str | None:
    """
    Scan text for prompt injection patterns. Replace matches with [REDACTED].
    """
    if text is None:
        return None
    sanitized = _INJECTION_PATTERNS.sub("[REDACTED]", text)
    return sanitized


def has_injection(text: str | None) -> bool:
    """Check if text contains prompt injection patterns."""
    if text is None:
        return False
    return bool(_INJECTION_PATTERNS.search(text))


# ─── Correlation ID Middleware ──────────────────────────────────────────────
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Inject X-Correlation-ID header on every request/response."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(
            "x-correlation-id", str(uuid.uuid4()),
        )
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


# ─── Request Logging Middleware ─────────────────────────────────────────────
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request: method, path, status, duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000.0

        user_id = "anonymous"
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id

        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id": user_id,
                "correlation_id": getattr(
                    request.state, "correlation_id", "unknown",
                ),
            },
        )
        return response


# ─── Global Exception Handler ──────────────────────────────────────────────
def setup_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import os
        env = os.getenv("ENVIRONMENT", "development")
        correlation_id = getattr(
            request.state, "correlation_id", "unknown",
        )

        logger.exception(
            "Unhandled exception",
            extra={"correlation_id": correlation_id},
        )

        detail = str(exc) if env == "development" else "An unexpected error occurred"

        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "correlation_id": correlation_id,
                "detail": detail,
            },
        )
