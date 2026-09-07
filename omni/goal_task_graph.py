"""Persistent goal/task DAG for JARVIS V9 supervised missions.

The graph records local planning/execution checkpoints only.  It cannot execute
external actions and deliberately keeps consequential actions in a durable
WAITING_APPROVAL state.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "state" / "goal_task_graphs.json"
MAX_GRAPHS = 100
MAX_TASKS = 200

TASK_STATES = frozenset({
    "PLANNED", "READY", "RUNNING", "WAITING_DEPENDENCY", "WAITING_APPROVAL",
    "BLOCKED", "FAILED_RETRYABLE", "FAILED_FINAL", "VERIFIED", "COMPLETED",
    "PAUSED", "CANCELLED",
})
TERMINAL_STATES = frozenset({"COMPLETED", "FAILED_FINAL", "CANCELLED"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


class GoalTaskGraphStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("graphs", [])
                return value
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass
        return {"version": 1, "graphs": [], "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def _find(self, graph_id: str) -> dict[str, Any]:
        value = str(graph_id or "").strip()
        for graph in self._state.get("graphs") or []:
            if graph.get("graph_id") == value:
                return graph
        raise KeyError("Unknown goal/task graph.")

    @staticmethod
    def _task(
        task_id: str,
        objective: str,
        *,
        status: str,
        dependencies: Iterable[str] = (),
        assigned_agent: str | None = None,
        required_tools: Iterable[str] = (),
        approval_required: bool = False,
    ) -> dict[str, Any]:
        if status not in TASK_STATES:
            raise ValueError(f"Unsupported task status: {status}")
        return {
            "task_id": str(task_id),
            "objective": _clean(objective, 1200),
            "status": status,
            "dependencies": [str(item) for item in dependencies],
            "assigned_agent": _clean(assigned_agent, 120) or None,
            "required_tools": [_clean(item, 120) for item in required_tools][:20],
            "evidence": [],
            "artifacts": [],
            "checkpoint": None,
            "retry_count": 0,
            "failure_reason": None,
            "approval_required": bool(approval_required),
            "created_at": _now(),
            "updated_at": _now(),
            "completed_at": None,
        }

    def create(
        self,
        objective: str,
        *,
        title: str = "",
        queue_id: str | None = None,
    ) -> dict[str, Any]:
        clean = _clean(objective, 8000)
        if len(clean) < 12:
            raise ValueError("Goal objective is too short.")
        graph_id = "goal-" + uuid4().hex[:16]
        tasks = [
            self._task("T00", "Frame objective and establish a bounded mission plan.", status="READY", assigned_agent="operator"),
            self._task("T10", "Execute supervised specialist mission and materialize local evidence.", status="WAITING_DEPENDENCY", dependencies=("T00",), assigned_agent="mission_control"),
            self._task("T20", "Verify mission packet, evidence coverage, and safety invariants.", status="WAITING_DEPENDENCY", dependencies=("T10",), assigned_agent="quality"),
            self._task(
                "A90",
                "Execute consequential external actions only after explicit human approval.",
                status="WAITING_DEPENDENCY",
                dependencies=("T20",),
                assigned_agent="human_approver",
                approval_required=True,
            ),
        ]
        graph = {
            "graph_id": graph_id,
            "queue_id": _clean(queue_id, 120) or None,
            "mission_id": None,
            "title": _clean(title, 160) or (clean[:157] + "…" if len(clean) > 160 else clean),
            "objective": clean,
            "status": "READY",
            "priority": 50,
            "tasks": tasks,
            "created_at": _now(),
            "updated_at": _now(),
            "completed_at": None,
            "pause_reason": None,
            "last_checkpoint": None,
            "paper_only": True,
            "live_execution": False,
            "external_actions": "APPROVAL_GATED",
        }
        with self._lock:
            graphs = list(self._state.get("graphs") or [])
            graphs.insert(0, graph)
            self._state["graphs"] = graphs[:MAX_GRAPHS]
            self._state["updated_at"] = graph["updated_at"]
            self._save()
        return json.loads(json.dumps(graph))

    def ensure_for_queue(self, queue_item: dict[str, Any]) -> dict[str, Any]:
        queue_id = str(queue_item.get("queue_id") or "")
        with self._lock:
            for graph in self._state.get("graphs") or []:
                if graph.get("queue_id") == queue_id:
                    return json.loads(json.dumps(graph))
        return self.create(
            str(queue_item.get("objective") or ""),
            title=str(queue_item.get("title") or ""),
            queue_id=queue_id,
        )

    @staticmethod
    def _dependencies_satisfied(graph: dict[str, Any], task: dict[str, Any]) -> bool:
        by_id = {row.get("task_id"): row for row in graph.get("tasks") or []}
        for dependency in task.get("dependencies") or []:
            row = by_id.get(dependency)
            if row is None or row.get("status") not in {"VERIFIED", "COMPLETED"}:
                return False
        return True

    def _refresh_ready(self, graph: dict[str, Any]) -> None:
        for task in graph.get("tasks") or []:
            if task.get("status") != "WAITING_DEPENDENCY":
                continue
            if not self._dependencies_satisfied(graph, task):
                continue
            task["status"] = "WAITING_APPROVAL" if task.get("approval_required") else "READY"
            task["updated_at"] = _now()

    def update_task(
        self,
        graph_id: str,
        task_id: str,
        status: str,
        *,
        evidence: dict[str, Any] | None = None,
        artifact: dict[str, Any] | None = None,
        checkpoint: dict[str, Any] | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        if status not in TASK_STATES:
            raise ValueError(f"Unsupported task status: {status}")
        with self._lock:
            graph = self._find(graph_id)
            task = next((row for row in graph.get("tasks") or [] if row.get("task_id") == task_id), None)
            if task is None:
                raise KeyError("Unknown task.")
            if status in {"READY", "RUNNING", "VERIFIED", "COMPLETED"} and not self._dependencies_satisfied(graph, task):
                raise RuntimeError("Task dependencies are not satisfied.")
            if task.get("approval_required") and status in {"READY", "RUNNING", "VERIFIED", "COMPLETED"}:
                raise PermissionError("Approval-required task cannot advance without the approval subsystem.")
            task["status"] = status
            task["updated_at"] = _now()
            if evidence is not None:
                task.setdefault("evidence", []).append(dict(evidence))
                task["evidence"] = task["evidence"][-30:]
            if artifact is not None:
                task.setdefault("artifacts", []).append(dict(artifact))
                task["artifacts"] = task["artifacts"][-30:]
            if checkpoint is not None:
                task["checkpoint"] = dict(checkpoint)
                graph["last_checkpoint"] = {"task_id": task_id, **dict(checkpoint)}
            if failure_reason:
                task["failure_reason"] = _clean(failure_reason, 500)
                if status == "FAILED_RETRYABLE":
                    task["retry_count"] = int(task.get("retry_count") or 0) + 1
            if status in {"VERIFIED", "COMPLETED"}:
                task["completed_at"] = _now()
            self._refresh_ready(graph)
            actionable = [row for row in graph.get("tasks") or [] if not row.get("approval_required")]
            if actionable and all(row.get("status") in {"VERIFIED", "COMPLETED"} for row in actionable):
                graph["status"] = "LOCAL_WORK_COMPLETED"
                graph["completed_at"] = _now()
            elif any(row.get("status") == "RUNNING" for row in graph.get("tasks") or []):
                graph["status"] = "RUNNING"
            elif any(row.get("status") == "FAILED_FINAL" for row in graph.get("tasks") or []):
                graph["status"] = "FAILED_FINAL"
            elif graph.get("status") != "PAUSED":
                graph["status"] = "READY"
            graph["updated_at"] = _now()
            self._state["updated_at"] = graph["updated_at"]
            self._save()
            return json.loads(json.dumps(graph))

    def attach_mission(self, graph_id: str, mission: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            graph = self._find(graph_id)
            graph["mission_id"] = _clean(mission.get("id"), 120) or None
            graph["mission_snapshot"] = {
                "id": mission.get("id"),
                "title": mission.get("title"),
                "status": mission.get("status"),
                "critic": mission.get("critic"),
                "tasks": mission.get("tasks"),
                "artifacts": mission.get("artifacts"),
            }
            graph["updated_at"] = _now()
            self._state["updated_at"] = graph["updated_at"]
            self._save()
            return json.loads(json.dumps(graph))

    def pause(self, graph_id: str, reason: str = "Operator pause") -> dict[str, Any]:
        with self._lock:
            graph = self._find(graph_id)
            if graph.get("status") in TERMINAL_STATES:
                return json.loads(json.dumps(graph))
            graph["status"] = "PAUSED"
            graph["pause_reason"] = _clean(reason, 300)
            graph["updated_at"] = _now()
            self._save()
            return json.loads(json.dumps(graph))

    def resume(self, graph_id: str) -> dict[str, Any]:
        with self._lock:
            graph = self._find(graph_id)
            if graph.get("status") != "PAUSED":
                return json.loads(json.dumps(graph))
            graph["status"] = "READY"
            graph["pause_reason"] = None
            self._refresh_ready(graph)
            graph["updated_at"] = _now()
            self._save()
            return json.loads(json.dumps(graph))

    def graph(self, graph_id: str) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._find(graph_id)))

    def snapshot(self, limit: int = 30) -> dict[str, Any]:
        limit = max(1, min(int(limit), MAX_GRAPHS))
        with self._lock:
            graphs = json.loads(json.dumps((self._state.get("graphs") or [])[:limit]))
            updated_at = self._state.get("updated_at")
        counts: dict[str, int] = {}
        for graph in graphs:
            status = str(graph.get("status") or "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1
        return {
            "success": True,
            "version": "9.2",
            "updated_at": updated_at,
            "counts": counts,
            "graphs": graphs,
            "persistent": True,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
        }


GOAL_TASK_GRAPHS = GoalTaskGraphStore()

__all__ = ["GOAL_TASK_GRAPHS", "GoalTaskGraphStore", "TASK_STATES"]
