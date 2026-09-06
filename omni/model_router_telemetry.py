"""Bounded persistent telemetry for JARVIS model routing.

This file records routing and optional execution outcomes.  It does not enable
cloud providers, transmit prompts, or alter privacy policy automatically.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "state" / "model_router_telemetry.json"
MAX_EVENTS = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelRouterTelemetry:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except (FileNotFoundError, OSError, ValueError):
            pass
        return {"version": 1, "events": [], "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def record(
        self,
        *,
        task_type: str,
        profile_id: str | None,
        provider: str | None = None,
        model: str | None = None,
        status: str = "SELECTED",
        latency_ms: float | None = None,
        quality_score: float | None = None,
        local: bool | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        event = {
            "at": _now(),
            "task_type": str(task_type or "unknown")[:120],
            "profile_id": str(profile_id or "") or None,
            "provider": str(provider or "") or None,
            "model": str(model or "") or None,
            "status": str(status or "UNKNOWN").upper()[:40],
            "latency_ms": max(0.0, float(latency_ms)) if latency_ms is not None else None,
            "quality_score": max(0.0, min(1.0, float(quality_score))) if quality_score is not None else None,
            "local": bool(local) if local is not None else None,
            "reason": str(reason or "")[:240],
        }
        with self._lock:
            events = list(self._state.get("events") or [])
            events.append(event)
            self._state["events"] = events[-MAX_EVENTS:]
            self._state["updated_at"] = event["at"]
            self._save()
        return event

    def status(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._state.get("events") or [])
            updated_at = self._state.get("updated_at")
        buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"events": 0, "successes": 0, "failures": 0, "latencies": [], "qualities": []}
        )
        for event in events:
            key = str(event.get("profile_id") or "UNAVAILABLE")
            bucket = buckets[key]
            bucket["events"] += 1
            status = str(event.get("status") or "").upper()
            if status in {"SELECTED", "SUCCEEDED", "OK"}:
                bucket["successes"] += 1
            if status in {"FAILED", "ERROR", "UNAVAILABLE", "REJECTED"}:
                bucket["failures"] += 1
            if event.get("latency_ms") is not None:
                bucket["latencies"].append(float(event["latency_ms"]))
            if event.get("quality_score") is not None:
                bucket["qualities"].append(float(event["quality_score"]))
        profiles: list[dict[str, Any]] = []
        for profile_id, bucket in sorted(buckets.items()):
            latencies = bucket.pop("latencies")
            qualities = bucket.pop("qualities")
            total = int(bucket["events"])
            profiles.append(
                {
                    "profile_id": profile_id,
                    **bucket,
                    "success_rate": (bucket["successes"] / total) if total else None,
                    "average_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
                    "average_quality_score": (sum(qualities) / len(qualities)) if qualities else None,
                }
            )
        return {
            "success": True,
            "version": "7.0",
            "event_count": len(events),
            "updated_at": updated_at,
            "profiles": profiles,
            "recent": events[-40:],
            "privacy_policy_changed": False,
            "cloud_enabled_by_telemetry": False,
        }


MODEL_ROUTER_TELEMETRY = ModelRouterTelemetry()


__all__ = ["MODEL_ROUTER_TELEMETRY", "ModelRouterTelemetry"]
