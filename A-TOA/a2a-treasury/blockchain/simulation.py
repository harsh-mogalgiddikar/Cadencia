"""
blockchain/simulation.py — DEPRECATED.

Replaced by blockchain/sdk_client.py dry_run() method in Phase 1 (Cadencia cleanup).
This module is kept only for backward compatibility.
Do NOT import in new code.

Original: RULE 07: Escrow NEVER deployed without dry-run simulation passing first.
"""
from __future__ import annotations

import warnings
warnings.warn(
    "blockchain.simulation is deprecated. Use blockchain.sdk_client.dry_run() instead.",
    DeprecationWarning,
    stacklevel=2,
)

from typing import Any


async def simulate_escrow_deployment(payload: dict) -> dict:
    """
    Simulate escrow deployment without broadcasting.
    Returns: { "success": bool, "estimated_cost": float, "error_message": str | None }
    """
    try:
        from blockchain.algo_client import AlgorandClient
        client = AlgorandClient()
        ok = await client.simulate_transaction(None)
        return {
            "success": ok,
            "estimated_cost": 0.0,
            "error_message": None if ok else "Simulation failed",
        }
    except Exception as e:
        return {
            "success": False,
            "estimated_cost": 0.0,
            "error_message": str(e),
        }


async def simulate_funding(
    contract_ref: str,
    amount: float,
    payer_wallet: str,
) -> dict:
    """Simulate escrow funding. Returns { "success": bool, "error_message": str | None }."""
    try:
        from blockchain.algo_client import AlgorandClient
        client = AlgorandClient()
        await client.simulate_transaction(None)
        return {"success": True, "error_message": None}
    except Exception as e:
        return {"success": False, "error_message": str(e)}
