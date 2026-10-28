"""JARVIS V20 bounded multi-agent orchestration mesh.

The mesh is a control plane, not a second trading engine. Existing V16/V17
engines remain authoritative. Agents execute independently through the
capability registry, while this service owns bounded concurrency, lifecycle,
health, and routing metadata.

All trading activity is paper/research only.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import Any
from uuid import uuid4

from omni.agent_registry import AgentRegistry, AgentRequest, default_agent_specs


ROLE_TO_AGENT = {
    "research": "research",
    "market_analysis": "trading",
    "intraday": "trading",
    "swing": "trading",
    "investment": "trading",
    "options": "trading",
    "risk": "quality",
    "system_health": "health",
    "learning": "learning",
}


@dataclass
class AgentLane:
    role: str
    agent: str
    status: str = "IDLE"
    submitted: int = 0
    completed: int = 0
    failed: int = 0
    last_task_id: str | None = None
    last_error: str | None = None
    last_finished_monotonic: float | None = None
    future: Future | None = field(default=None, repr=False)


class V20AgentMesh:
    """Bounded concurrent dispatcher for independent JARVIS specialist lanes."""

    def __init__(self, *, max_workers: int = 6, registry: AgentRegistry | None = None):
        if not 2 <= int(max_workers) <= 12:
            raise ValueError("max_workers must be between 2 and 12.")
        self.max_workers = int(max_workers)
        self.registry = registry or AgentRegistry(default_agent_specs())
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="jarvis-agent",
        )
        self._lock = RLock()
        self._started = monotonic()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lanes = {
            role: AgentLane(role=role, agent=agent)
            for role, agent in ROLE_TO_AGENT.items()
        }

    def submit(self, role: str, prompt: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        role = str(role or "").strip().lower()
        prompt = str(prompt or "").strip()
        if role not in self._lanes:
            raise ValueError(f"Unknown JARVIS V20 agent lane: {role}")
        if not prompt:
            raise ValueError("Agent prompt cannot be empty.")

        task_id = uuid4().hex
        lane = self._lanes[role]
        payload = dict(context or {})
        payload.update({
            "workspace": str(payload.get("workspace") or "INTRADAY").upper(),
            "paper_only": True,
            "live_execution": False,
            "mesh_task_id": task_id,
        })

        with self._lock:
            lane.status = "RUNNING"
            lane.submitted += 1
            lane.last_task_id = task_id
            lane.last_error = None
            self._tasks[task_id] = {
                "task_id": task_id,
                "role": role,
                "agent": lane.agent,
                "status": "RUNNING",
                "submitted_at_monotonic": monotonic(),
            }
            future = self._pool.submit(self._execute, task_id, role, prompt, payload)
            lane.future = future

        return self.task_status(task_id)

    def _execute(self, task_id: str, role: str, prompt: str, context: dict[str, Any]) -> None:
        lane = self._lanes[role]
        try:
            request = AgentRequest(
                agent=lane.agent,
                text=prompt,
                required_capabilities=frozenset(),
            )
            response = self.registry.execute(request)
            success = bool(response.success)
            result = {
                "success": success,
                "agent": lane.agent,
                "message": response.message,
                "data": response.data,
                "error_type": response.error_type,
            }
            with self._lock:
                task = self._tasks[task_id]
                task.update({
                    "status": "SUCCEEDED" if success else "FAILED",
                    "finished_at_monotonic": monotonic(),
                    "result": result,
                })
                lane.status = "IDLE"
                lane.completed += int(success)
                lane.failed += int(not success)
                lane.last_error = response.error_type
                lane.last_finished_monotonic = monotonic()
        except Exception as exc:
            with self._lock:
                self._tasks[task_id].update({
                    "status": "FAILED",
                    "finished_at_monotonic": monotonic(),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                lane.status = "IDLE"
                lane.failed += 1
                lane.last_error = f"{type(exc).__name__}: {exc}"[:300]
                lane.last_finished_monotonic = monotonic()

    def task_status(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = dict(self._tasks.get(task_id) or {})
        if not task:
            return {"success": False, "message": "Unknown mesh task."}
        return {
            "success": True,
            **task,
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            lanes = {
                role: {
                    "role": lane.role,
                    "agent": lane.agent,
                    "status": lane.status,
                    "submitted": lane.submitted,
                    "completed": lane.completed,
                    "failed": lane.failed,
                    "last_task_id": lane.last_task_id,
                    "last_error": lane.last_error,
                }
                for role, lane in self._lanes.items()
            }
            active = sum(lane.status == "RUNNING" for lane in self._lanes.values())
            tasks = len(self._tasks)
        return {
            "success": True,
            "service": "JARVIS_V20_MULTI_AGENT_MESH",
            "version": "20.1",
            "state": "RUNNING",
            "max_workers": self.max_workers,
            "active_lanes": active,
            "known_tasks": tasks,
            "lanes": lanes,
            "paper_only": True,
            "live_execution": False,
            "live_orders_locked": True,
        }

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


agent_mesh = V20AgentMesh(max_workers=6)

__all__ = ["V20AgentMesh", "agent_mesh", "ROLE_TO_AGENT"]
