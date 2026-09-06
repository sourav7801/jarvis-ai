"""Persistent, resumable local queue for supervised JARVIS missions.

The queue owns scheduling state only.  It never executes external actions and
never bypasses Mission Control approval locks.  A worker must explicitly lease
a queued item and provide the mission executor.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "state" / "mission_queue.json"
MAX_ITEMS = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionQueue:
    def __init__(self, path: Path | str | None = None, *, lease_seconds: int = 300) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self.lease_seconds = max(30, min(int(lease_seconds), 3600))
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("items", [])
                return value
        except (FileNotFoundError, OSError, ValueError):
            pass
        return {"version": 1, "items": [], "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def enqueue(self, objective: str, *, title: str = "", priority: int = 50) -> dict[str, Any]:
        clean = " ".join(str(objective or "").split())
        if len(clean) < 12:
            raise ValueError("Mission objective is too short for durable queueing.")
        item = {
            "queue_id": "queue-" + uuid4().hex[:16],
            "objective": clean[:8000],
            "title": " ".join(str(title or "").split())[:160],
            "priority": max(0, min(int(priority), 100)),
            "status": "QUEUED",
            "created_at": _now(),
            "updated_at": _now(),
            "attempts": 0,
            "lease_owner": None,
            "lease_expires_at": None,
            "mission_id": None,
            "error": None,
            "approval_boundary": "Mission execution remains supervised; consequential external actions stay locked.",
        }
        with self._lock:
            items = list(self._state.get("items") or [])
            items.append(item)
            items.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("created_at") or "")))
            self._state["items"] = items[-MAX_ITEMS:]
            self._state["updated_at"] = item["updated_at"]
            self._save()
        return dict(item)

    def recover_expired_leases(self, *, now_epoch: float | None = None) -> int:
        now_value = time.time() if now_epoch is None else float(now_epoch)
        recovered = 0
        with self._lock:
            for item in self._state.get("items") or []:
                if item.get("status") != "LEASED":
                    continue
                expires = item.get("lease_expires_at")
                if expires is not None and float(expires) <= now_value:
                    item["status"] = "QUEUED"
                    item["lease_owner"] = None
                    item["lease_expires_at"] = None
                    item["updated_at"] = _now()
                    item["error"] = "Previous worker lease expired; item returned to queue."
                    recovered += 1
            if recovered:
                self._state["updated_at"] = _now()
                self._save()
        return recovered

    def lease_next(self, worker_id: str) -> dict[str, Any] | None:
        worker = str(worker_id or "").strip()
        if not worker:
            raise ValueError("worker_id is required")
        self.recover_expired_leases()
        now_value = time.time()
        with self._lock:
            queued = [item for item in self._state.get("items") or [] if item.get("status") == "QUEUED"]
            if not queued:
                return None
            queued.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("created_at") or "")))
            item = queued[0]
            item["status"] = "LEASED"
            item["lease_owner"] = worker[:120]
            item["lease_expires_at"] = now_value + self.lease_seconds
            item["attempts"] = int(item.get("attempts") or 0) + 1
            item["updated_at"] = _now()
            self._state["updated_at"] = item["updated_at"]
            self._save()
            return dict(item)

    def complete(self, queue_id: str, *, mission_id: str, worker_id: str) -> dict[str, Any]:
        return self._finish(queue_id, "SUCCEEDED", worker_id, mission_id=mission_id)

    def fail(self, queue_id: str, *, worker_id: str, error: str, retry: bool = True) -> dict[str, Any]:
        return self._finish(queue_id, "QUEUED" if retry else "FAILED", worker_id, error=error)

    def cancel(self, queue_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._find(queue_id)
            if item.get("status") in {"SUCCEEDED", "CANCELLED"}:
                return dict(item)
            item["status"] = "CANCELLED"
            item["lease_owner"] = None
            item["lease_expires_at"] = None
            item["updated_at"] = _now()
            self._state["updated_at"] = item["updated_at"]
            self._save()
            return dict(item)

    def _find(self, queue_id: str) -> dict[str, Any]:
        value = str(queue_id or "").strip()
        for item in self._state.get("items") or []:
            if item.get("queue_id") == value:
                return item
        raise KeyError("Unknown mission queue item.")

    def _finish(
        self,
        queue_id: str,
        status: str,
        worker_id: str,
        *,
        mission_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        worker = str(worker_id or "").strip()
        with self._lock:
            item = self._find(queue_id)
            if item.get("status") != "LEASED" or item.get("lease_owner") != worker:
                raise PermissionError("Only the active lease owner may finish this queue item.")
            item["status"] = status
            item["lease_owner"] = None
            item["lease_expires_at"] = None
            item["mission_id"] = str(mission_id or "") or item.get("mission_id")
            item["error"] = str(error or "")[:500] or None
            item["updated_at"] = _now()
            self._state["updated_at"] = item["updated_at"]
            self._save()
            return dict(item)

    def snapshot(self) -> dict[str, Any]:
        self.recover_expired_leases()
        with self._lock:
            items = [dict(item) for item in self._state.get("items") or []]
            updated = self._state.get("updated_at")
        counts: dict[str, int] = {}
        for item in items:
            status = str(item.get("status") or "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1
        return {
            "success": True,
            "version": "7.0",
            "updated_at": updated,
            "counts": counts,
            "items": items[-100:],
            "resumable": True,
            "external_actions": "APPROVAL_GATED",
            "live_execution": False,
        }


MISSION_QUEUE = MissionQueue()


__all__ = ["MISSION_QUEUE", "MissionQueue"]
