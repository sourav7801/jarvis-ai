"""Persistent due-time contract for evidence-first opportunity radar runs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable


class OpportunityRadarScheduler:
    def __init__(self, state_path: Path, interval_hours: int = 24):
        self.state_path = Path(state_path)
        self.interval_hours = max(1, min(int(interval_hours), 168))
        self._lock = RLock()
        self._state: dict[str, Any] = {"version": 1, "schedules": {}}
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("schedules"), dict):
                self._state = loaded
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.state_path)

    def enroll(self, plan_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        timestamp = now or self._now()
        with self._lock:
            schedule = self._state["schedules"].setdefault(str(plan_id), {})
            schedule.update({
                "plan_id": str(plan_id), "enabled": True,
                "interval_hours": self.interval_hours,
                "next_due_at": schedule.get("next_due_at") or timestamp.isoformat(),
                "last_run_at": schedule.get("last_run_at"),
                "last_status": schedule.get("last_status", "DUE"),
            })
            self._save()
            return dict(schedule)

    def run_if_due(self, plan_id: str, runner: Callable[[], dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any]:
        timestamp = now or self._now()
        with self._lock:
            schedule = self._state["schedules"].get(str(plan_id))
            if not schedule or not schedule.get("enabled"):
                return {"ran": False, "status": "NOT_ENROLLED"}
            if timestamp < datetime.fromisoformat(schedule["next_due_at"]):
                return {"ran": False, "status": "NOT_DUE", "next_due_at": schedule["next_due_at"]}
        try:
            result = runner()
            status = "EVIDENCE_READY" if isinstance(result, dict) else "INVALID_RESULT"
        except Exception as error:
            result = {"error_type": type(error).__name__}
            status = "FAILED_SAFE"
        with self._lock:
            schedule = self._state["schedules"][str(plan_id)]
            schedule.update({
                "last_run_at": timestamp.isoformat(), "last_status": status,
                "next_due_at": (timestamp + timedelta(hours=schedule["interval_hours"])).isoformat(),
            })
            self._save()
        return {"ran": True, "status": status, "result": result, "next_due_at": schedule["next_due_at"]}

    def snapshot(self, plan_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            if plan_id is not None:
                return dict(self._state["schedules"].get(str(plan_id), {}))
            return json.loads(json.dumps(self._state))
