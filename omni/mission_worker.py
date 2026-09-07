"""Bounded background worker for JARVIS V9 supervised local missions.

The worker consumes MissionQueue items, persists a GoalTaskGraph, renews leases,
and delegates only to MissionControl's existing local/supervised packet builder.
It has no broker surface and no authority to execute consequential external
steps; those remain durable WAITING_APPROVAL nodes.
"""
from __future__ import annotations

import os
import socket
import threading
import time
from typing import Any
from uuid import uuid4

from .agent_registry import AgentRegistry, default_agent_specs
from .goal_task_graph import GOAL_TASK_GRAPHS, GoalTaskGraphStore
from .mission_control import MissionControl
from .mission_queue import MISSION_QUEUE, MissionQueue


class MissionWorker:
    def __init__(
        self,
        *,
        queue: MissionQueue | None = None,
        graphs: GoalTaskGraphStore | None = None,
        mission_control: MissionControl | None = None,
        worker_id: str | None = None,
        poll_seconds: float = 2.0,
        max_attempts: int = 3,
    ) -> None:
        self.queue = queue or MISSION_QUEUE
        self.graphs = graphs or GOAL_TASK_GRAPHS
        self.mission_control = mission_control or MissionControl(AgentRegistry(default_agent_specs()))
        default_id = f"jarvis-mission-{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"
        self.worker_id = str(worker_id or default_id)[:120]
        self.poll_seconds = max(0.25, min(float(poll_seconds), 60.0))
        self.max_attempts = max(1, min(int(max_attempts), 10))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active_queue_id: str | None = None
        self._active_graph_id: str | None = None
        self._last_result: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._cycles = 0
        self._completed = 0
        self._failed = 0

    def _heartbeat_loop(self, queue_id: str, stop: threading.Event) -> None:
        interval = max(10.0, min(float(self.queue.lease_seconds) / 3.0, 60.0))
        while not stop.wait(interval):
            try:
                self.queue.heartbeat(queue_id, worker_id=self.worker_id)
            except (KeyError, PermissionError, RuntimeError):
                return

    def enqueue(self, objective: str, *, title: str = "", priority: int = 50) -> dict[str, Any]:
        return self.queue.enqueue(objective, title=title, priority=priority)

    def run_once(self) -> dict[str, Any]:
        with self._lock:
            if self._active_queue_id is not None:
                return {
                    "success": False,
                    "state": "BUSY",
                    "queue_id": self._active_queue_id,
                    "paper_only": True,
                    "live_execution": False,
                }
        item = self.queue.lease_next(self.worker_id)
        self._cycles += 1
        if item is None:
            result = {
                "success": True,
                "state": "IDLE",
                "message": "No queued supervised missions.",
                "paper_only": True,
                "live_execution": False,
            }
            self._last_result = result
            return result

        queue_id = str(item["queue_id"])
        graph = self.graphs.ensure_for_queue(item)
        graph_id = str(graph["graph_id"])
        with self._lock:
            self._active_queue_id = queue_id
            self._active_graph_id = graph_id
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(queue_id, heartbeat_stop),
            daemon=True,
            name="jarvis-mission-heartbeat",
        )
        heartbeat.start()
        current_task = "T00"
        try:
            self.queue.checkpoint(
                queue_id,
                worker_id=self.worker_id,
                graph_id=graph_id,
                checkpoint={"phase": "GRAPH_READY", "task_id": "T00"},
            )
            self.graphs.update_task(graph_id, "T00", "RUNNING", checkpoint={"phase": "PLANNING"})
            self.graphs.update_task(
                graph_id,
                "T00",
                "VERIFIED",
                evidence={"kind": "queue_lease", "queue_id": queue_id, "worker_id": self.worker_id},
                checkpoint={"phase": "PLAN_VERIFIED"},
            )

            current_task = "T10"
            self.queue.heartbeat(queue_id, worker_id=self.worker_id)
            self.graphs.update_task(graph_id, "T10", "RUNNING", checkpoint={"phase": "MISSION_CONTROL"})
            mission = self.mission_control.create_mission(
                str(item.get("objective") or ""),
                title=str(item.get("title") or "") or None,
            )
            self.graphs.attach_mission(graph_id, mission)
            self.queue.checkpoint(
                queue_id,
                worker_id=self.worker_id,
                graph_id=graph_id,
                mission_id=str(mission.get("id") or ""),
                checkpoint={"phase": "MISSION_PACKET_CREATED", "task_id": "T10"},
            )
            self.graphs.update_task(
                graph_id,
                "T10",
                "VERIFIED",
                evidence={
                    "kind": "mission_packet",
                    "mission_id": mission.get("id"),
                    "status": mission.get("status"),
                    "specialists": len(mission.get("selected_agents") or []),
                },
                artifact={"kind": "mission_workspace", "artifacts": mission.get("artifacts") or []},
                checkpoint={"phase": "MISSION_PACKET_VERIFIED"},
            )

            current_task = "T20"
            self.queue.heartbeat(queue_id, worker_id=self.worker_id)
            self.graphs.update_task(graph_id, "T20", "RUNNING", checkpoint={"phase": "VERIFY"})
            critic = dict(mission.get("critic") or {})
            verified = critic.get("verdict") == "VERIFIED_LOCAL_PACKET"
            if not verified:
                self.graphs.update_task(
                    graph_id,
                    "T20",
                    "BLOCKED",
                    evidence={"kind": "critic", "verdict": critic.get("verdict"), "confidence": critic.get("confidence")},
                    failure_reason="Mission packet requires human review before further progression.",
                )
                finished = self.queue.fail(
                    queue_id,
                    worker_id=self.worker_id,
                    error="Mission packet requires human review.",
                    retry=False,
                )
                self._failed += 1
                result = {
                    "success": False,
                    "state": "REVIEW_REQUIRED",
                    "queue": finished,
                    "graph": self.graphs.graph(graph_id),
                    "mission_id": mission.get("id"),
                    "paper_only": True,
                    "live_execution": False,
                    "external_actions": "APPROVAL_GATED",
                }
                self._last_result = result
                return result

            self.graphs.update_task(
                graph_id,
                "T20",
                "VERIFIED",
                evidence={
                    "kind": "critic",
                    "verdict": critic.get("verdict"),
                    "confidence": critic.get("confidence"),
                    "checks": critic.get("checks") or {},
                },
                checkpoint={"phase": "LOCAL_WORK_VERIFIED"},
            )
            finished = self.queue.complete(
                queue_id,
                mission_id=str(mission.get("id") or ""),
                worker_id=self.worker_id,
            )
            self._completed += 1
            result = {
                "success": True,
                "state": "LOCAL_WORK_COMPLETED",
                "queue": finished,
                "graph": self.graphs.graph(graph_id),
                "mission_id": mission.get("id"),
                "approval_task": "A90",
                "external_actions": "APPROVAL_GATED",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }
            self._last_result = result
            self._last_error = None
            return result
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"[:500]
            self._last_error = text
            try:
                attempts = int(item.get("attempts") or 1)
                retry = attempts < self.max_attempts
                task_state = "FAILED_RETRYABLE" if retry else "FAILED_FINAL"
                self.graphs.update_task(
                    graph_id,
                    current_task,
                    task_state,
                    failure_reason=text,
                    checkpoint={"phase": "FAILED", "retry": retry},
                )
                finished = self.queue.fail(
                    queue_id,
                    worker_id=self.worker_id,
                    error=text,
                    retry=retry,
                )
            except Exception as finish_error:
                finished = {"queue_id": queue_id, "status": "UNKNOWN", "finish_error": type(finish_error).__name__}
            self._failed += 1
            result = {
                "success": False,
                "state": "FAILED_RETRYABLE" if int(item.get("attempts") or 1) < self.max_attempts else "FAILED_FINAL",
                "error": text,
                "queue": finished,
                "graph_id": graph_id,
                "paper_only": True,
                "live_execution": False,
            }
            self._last_result = result
            return result
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1.0)
            with self._lock:
                self._active_queue_id = None
                self._active_graph_id = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self.poll_seconds)

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.status()
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="jarvis-mission-worker")
            self._thread.start()
        return self.status()

    def stop(self, *, wait_seconds: float = 0.0) -> dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread is not None and wait_seconds > 0:
            thread.join(timeout=max(0.0, min(float(wait_seconds), 30.0)))
        return self.status()

    def pause_item(self, queue_id: str) -> dict[str, Any]:
        item = self.queue.pause(queue_id)
        graph_id = item.get("graph_id")
        if graph_id:
            self.graphs.pause(str(graph_id), "Queue item paused by operator")
        return item

    def resume_item(self, queue_id: str) -> dict[str, Any]:
        item = self.queue.resume(queue_id)
        graph_id = item.get("graph_id")
        if graph_id:
            self.graphs.resume(str(graph_id))
        return item

    def status(self) -> dict[str, Any]:
        thread = self._thread
        return {
            "success": True,
            "version": "9.2",
            "worker_id": self.worker_id,
            "running": bool(thread is not None and thread.is_alive() and not self._stop.is_set()),
            "stop_requested": self._stop.is_set(),
            "active_queue_id": self._active_queue_id,
            "active_graph_id": self._active_graph_id,
            "cycles": self._cycles,
            "completed": self._completed,
            "failed": self._failed,
            "last_error": self._last_error,
            "last_result": self._last_result,
            "queue": self.queue.snapshot(limit=30),
            "graphs": self.graphs.snapshot(limit=20),
            "bounded_concurrency": 1,
            "external_actions": "APPROVAL_GATED",
            "automatic_production_rewrite": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


MISSION_WORKER = MissionWorker()

__all__ = ["MISSION_WORKER", "MissionWorker"]
