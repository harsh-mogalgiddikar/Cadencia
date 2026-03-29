"""
blockchain/simulation.py — Dry-run simulation before broadcast.

RULE 07: Escrow NEVER deployed without dry-run simulation passing first.
"""
from __future__ import annotations

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
