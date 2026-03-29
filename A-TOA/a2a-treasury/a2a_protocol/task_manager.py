"""
a2a_protocol/task_manager.py — A2A Task Lifecycle Manager.

Neutral Protocol Engine. Routes all agent actions as A2A Tasks.
Lifecycle: submitted → working → completed | failed
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel

from db.audit_logger import AuditLogger

TASK_KEY_PREFIX = "a2a_task"
SESSION_TASKS_KEY = "a2a_session_tasks"
TASK_TTL = 3600
audit_logger = AuditLogger()


class A2ATaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ATask(BaseModel):
    task_id: str
    session_id: str
    from_agent: str
    to_agent: str
    task_type: str
    payload: dict
    status: A2ATaskStatus
    created_at: str
    completed_at: str | None = None
    error: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class A2ATaskManager:
    """Neutral Protocol Engine. Routes all agent actions as A2A Tasks."""

    def _task_key(self, task_id: str) -> str:
        return f"{TASK_KEY_PREFIX}:{task_id}"

    async def submit_task(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        task_type: str,
        payload: dict,
        redis_client: Any,
    ) -> A2ATask:
        """Create a new A2ATask, store in Redis, transition SUBMITTED → WORKING."""
        task_id = str(uuid.uuid4())
        now = _now_iso()
        task = A2ATask(
            task_id=task_id,
            session_id=session_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task_type=task_type,
            payload=payload,
            status=A2ATaskStatus.WORKING,
            created_at=now,
            completed_at=None,
            error=None,
        )
        key = self._task_key(task_id)
        await redis_client.client.set(
            key,
            json.dumps(task.model_dump(mode="json"), default=str),
            ex=TASK_TTL,
        )
        session_set_key = f"{SESSION_TASKS_KEY}:{session_id}"
        await redis_client.client.sadd(session_set_key, task_id)
        await redis_client.client.expire(session_set_key, TASK_TTL)
        return task

    async def complete_task(
        self,
        task_id: str,
        result_payload: dict,
        redis_client: Any,
        db_session: Any,
    ) -> A2ATask:
        """Transition task WORKING → COMPLETED."""
        key = self._task_key(task_id)
        raw = await redis_client.client.get(key)
        if not raw:
            raise ValueError(f"Task not found: {task_id}")
        data = json.loads(raw)
        data["status"] = A2ATaskStatus.COMPLETED.value
        data["completed_at"] = _now_iso()
        data["payload"] = result_payload
        task = A2ATask(**data)
        await redis_client.client.set(
            key,
            json.dumps(task.model_dump(mode="json"), default=str),
            ex=TASK_TTL,
        )
        await audit_logger.append(
            entity_type="a2a_task",
            entity_id=task_id,
            action="A2A_TASK_COMPLETED",
            actor_id="neutral",
            payload={"task_id": task_id, "session_id": task.session_id},
            db_session=db_session,
        )
        return task

    async def fail_task(
        self,
        task_id: str,
        error_message: str,
        redis_client: Any,
        db_session: Any,
    ) -> A2ATask:
        """Transition task WORKING → FAILED."""
        key = self._task_key(task_id)
        raw = await redis_client.client.get(key)
        if not raw:
            raise ValueError(f"Task not found: {task_id}")
        data = json.loads(raw)
        data["status"] = A2ATaskStatus.FAILED.value
        data["completed_at"] = _now_iso()
        data["error"] = error_message
        task = A2ATask(**data)
        await redis_client.client.set(
            key,
            json.dumps(task.model_dump(mode="json"), default=str),
            ex=TASK_TTL,
        )
        await audit_logger.append(
            entity_type="a2a_task",
            entity_id=task_id,
            action="A2A_TASK_FAILED",
            actor_id="neutral",
            payload={"task_id": task_id, "error": error_message},
            db_session=db_session,
        )
        return task

    async def route_offer(
        self,
        session_id: str,
        action_envelope: dict,
        from_role: str,
        redis_client: Any,
        db_session: Any,
    ) -> A2ATask:
        """
        Route offer: from_role → neutral → counterpart.
        Validates envelope, calls state_machine.process_action, completes both tasks.
        """
        from api.schemas.session import AgentActionEnvelope
        from core.state_machine import DANPStateMachine

        state_machine = DANPStateMachine()
        counterpart = "seller" if from_role == "buyer" else "buyer"

        # 1. Submit task: from_role → neutral
        task1 = await self.submit_task(
            session_id=session_id,
            from_agent=from_role,
            to_agent="neutral",
            task_type="offer",
            payload=action_envelope,
            redis_client=redis_client,
        )
        await audit_logger.append(
            entity_type="a2a_task",
            entity_id=task1.task_id,
            action="A2A_TASK_SUBMITTED",
            actor_id=from_role,
            payload={"task_id": task1.task_id, "session_id": session_id},
            db_session=db_session,
        )

        # 2. Validate envelope
        try:
            AgentActionEnvelope(**action_envelope)
        except Exception as e:
            await self.fail_task(
                task1.task_id, str(e), redis_client, db_session
            )
            raise

        # 3. Process action via state machine
        try:
            result = await state_machine.process_action(
                action=action_envelope,
                db_session=db_session,
                redis_client=redis_client,
            )
        except Exception as e:
            await self.fail_task(
                task1.task_id, str(e), redis_client, db_session
            )
            raise

        # 4. Submit task: neutral → counterpart
        task2 = await self.submit_task(
            session_id=session_id,
            from_agent="neutral",
            to_agent=counterpart,
            task_type="offer",
            payload=result,
            redis_client=redis_client,
        )

        # 5. Complete both tasks
        await self.complete_task(
            task1.task_id, result, redis_client, db_session
        )
        await self.complete_task(
            task2.task_id, result, redis_client, db_session
        )
        return task2

    async def get_task(
        self,
        task_id: str,
        redis_client: Any,
    ) -> A2ATask | None:
        """Retrieve task from Redis by task_id."""
        key = self._task_key(task_id)
        raw = await redis_client.client.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return A2ATask(**data)

    async def get_session_tasks(
        self,
        session_id: str,
        redis_client: Any,
    ) -> list[A2ATask]:
        """Returns all tasks for a session from Redis."""
        session_set_key = f"{SESSION_TASKS_KEY}:{session_id}"
        task_ids = await redis_client.client.smembers(session_set_key)
        tasks = []
        for tid in task_ids or []:
            t = await self.get_task(tid, redis_client)
            if t:
                tasks.append(t)
        return sorted(tasks, key=lambda x: x.created_at)
