"""
agents/buyer_agent.py — Buyer agent orchestration.

Runs the buyer's side of the negotiation autonomously.
Polls session state; when it's buyer's turn, runs run_agent_turn.
NEVER imports from seller_agent. Shares logic via pipeline.run_agent_turn.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.pipeline import run_agent_turn
from a2a_protocol.task_manager import A2ATaskManager
from core.state_machine import TERMINAL_STATES

logger = logging.getLogger("a2a_treasury")


class BuyerAgent:
    """Autonomous buyer negotiation agent. Uses 4-layer pipeline via run_agent_turn."""

    async def run_session(
        self,
        session_id: str,
        db_session: Any,
        redis_client: Any,
        task_manager: A2ATaskManager,
    ) -> None:
        """
        Run the buyer's side. Poll session state every 1s.
        When expected_turn == buyer, execute run_agent_turn.
        Stop when session is terminal.
        """
        from agents.pipeline import _load_agent_config_dict

        while True:
            state = await redis_client.get_session_state(session_id)
            if state is None:
                state = await redis_client.rebuild_from_postgres(
                    session_id, db_session
                )
            if state is None:
                logger.warning("BuyerAgent: session %s not found", session_id)
                return
            if state.get("status") in TERMINAL_STATES:
                logger.info("BuyerAgent: session %s terminal %s", session_id, state["status"])
                return
            expected = state.get("expected_turn")
            if expected == "buyer":
                try:
                    agent_config = await _load_agent_config_dict(
                        state["buyer_enterprise_id"], "buyer", db_session
                    )
                    current_round = state.get("current_round", 1)
                    await run_agent_turn(
                        session_id=session_id,
                        agent_role="buyer",
                        current_round=current_round,
                        session_state=state,
                        agent_config=agent_config,
                        db_session=db_session,
                        redis_client=redis_client,
                        task_manager=task_manager,
                    )
                    # Successful action — sleep to respect rate limit (2s window)
                    await asyncio.sleep(2.5)
                    continue
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "Rate limit" in err_str:
                        logger.debug("BuyerAgent: rate-limited, backing off")
                        await asyncio.sleep(3.0)
                        continue
                    logger.exception("BuyerAgent run_agent_turn failed: %s", e)
            await asyncio.sleep(1.0)
