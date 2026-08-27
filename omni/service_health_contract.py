from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any


HEALTH_SCHEMA_VERSION = "JARVIS_SERVICE_HEALTH_V1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ServiceHealthClock:
    """Uniform process-local health, timing and safety envelope."""

    def __init__(self, service: str, version: str, *, paper_only: bool = True) -> None:
        self.service = str(service)
        self.version = str(version)
        self.paper_only = bool(paper_only)
        self.started_at = _utc_now()
        self._started_monotonic = time.monotonic()
        self._last_success_at: str | None = self.started_at
        self._last_error: str | None = None
        self._last_error_at: str | None = None
        self._lock = threading.RLock()

    def mark_success(self) -> None:
        with self._lock:
            self._last_success_at = _utc_now()

    def mark_error(self, error: Any) -> None:
        with self._lock:
            self._last_error = str(error or "UNKNOWN_ERROR")[:500]
            self._last_error_at = _utc_now()

    def payload(
        self,
        *,
        status: str,
        healthy: bool,
        last_error: Any | None = None,
        dependencies: dict[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        with self._lock:
            recorded_error = self._last_error
            last_error_at = self._last_error_at
            last_success_at = self._last_success_at
        resolved_error = str(last_error)[:500] if last_error else recorded_error
        return {
            "success": bool(healthy),
            "ok": bool(healthy),
            "health_schema": HEALTH_SCHEMA_VERSION,
            "service": self.service,
            "version": self.version,
            "status": str(status).upper(),
            "started_at": self.started_at,
            "uptime_seconds": round(max(time.monotonic() - self._started_monotonic, 0.0), 3),
            "response_generated_at": _utc_now(),
            "last_success_at": last_success_at,
            "last_error": resolved_error,
            "last_error_at": last_error_at,
            "dependencies": dict(dependencies or {}),
            "paper_only": self.paper_only,
            "live_execution": False,
            **extra,
        }
