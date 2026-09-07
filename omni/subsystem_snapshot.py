"""Bounded, fault-isolated subsystem snapshots for JARVIS operator surfaces.

The collector deliberately keeps provider execution local and read-only.  A slow
or broken subsystem must not make the aggregate Completion Center unavailable.
"""

from __future__ import annotations

import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)([^\s,;]+)"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password|passwd)\s*[:=]\s*)([^\s,;]+)"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_error(error: BaseException | str, *, limit: int = 500) -> str:
    """Return bounded diagnostic text with common credential forms redacted."""

    text = str(error).replace("\r", " ").replace("\n", " ")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "[REDACTED]", text)
    return text[: max(40, int(limit))]


class SubsystemSnapshotCollector:
    """Collect subsystem payloads with bounded concurrency and timeout isolation.

    At most one in-flight call per subsystem name is retained.  Repeated overview
    requests therefore reuse a timed-out call instead of spawning an unbounded
    number of background threads while a dependency is hung.
    """

    def __init__(self, *, max_inflight: int = 8) -> None:
        workers = max(1, min(int(max_inflight), 32))
        self.max_inflight = workers
        self._executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="jarvis-subsystem",
        )
        self._lock = threading.RLock()
        self._inflight: dict[str, tuple[Future[Any], float]] = {}

    @staticmethod
    def _record(
        *,
        state: str,
        healthy: bool,
        data: Any = None,
        error: str | None = None,
        last_updated: str | None = None,
        elapsed_ms: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "state": str(state),
            "healthy": bool(healthy),
            "data": data,
            "error": error,
            "last_updated": last_updated,
            "elapsed_ms": round(max(float(elapsed_ms), 0.0), 3),
        }

    def _future_for(self, name: str, provider: Callable[[], Any]) -> tuple[Future[Any], float]:
        with self._lock:
            existing = self._inflight.get(name)
            if existing is not None and not existing[0].done():
                return existing

            started = time.monotonic()
            future = self._executor.submit(provider)
            record = (future, started)
            self._inflight[name] = record
            return record

    def collect(
        self,
        providers: Mapping[str, Callable[[], Any]],
        *,
        timeout: float = 2.0,
    ) -> dict[str, dict[str, Any]]:
        timeout = max(0.0, float(timeout))
        active: dict[str, tuple[Future[Any], float]] = {}
        for raw_name, provider in providers.items():
            name = str(raw_name)
            if not callable(provider):
                active[name] = (Future(), time.monotonic())
                active[name][0].set_exception(TypeError("subsystem provider is not callable"))
                continue
            active[name] = self._future_for(name, provider)

        futures = {future for future, _started in active.values()}
        if futures:
            wait(futures, timeout=timeout)

        now = time.monotonic()
        completed_at = _utc_now()
        result: dict[str, dict[str, Any]] = {}

        for name, (future, started) in active.items():
            elapsed_ms = (now - started) * 1000.0
            if not future.done():
                result[name] = self._record(
                    state="TIMEOUT",
                    healthy=False,
                    error="Subsystem snapshot timed out.",
                    last_updated=None,
                    elapsed_ms=elapsed_ms,
                )
                continue

            try:
                value = future.result()
            except Exception as exc:  # subsystem boundary: isolate all provider failures
                result[name] = self._record(
                    state="FAILED",
                    healthy=False,
                    error=f"{type(exc).__name__}: {sanitize_error(exc)}",
                    last_updated=completed_at,
                    elapsed_ms=elapsed_ms,
                )
            else:
                explicitly_unhealthy = isinstance(value, dict) and value.get("success") is False
                result[name] = self._record(
                    state="DEGRADED" if explicitly_unhealthy else "READY",
                    healthy=not explicitly_unhealthy,
                    data=value,
                    error=(
                        sanitize_error(value.get("error") or value.get("message") or "Subsystem reported failure.")
                        if explicitly_unhealthy
                        else None
                    ),
                    last_updated=completed_at,
                    elapsed_ms=elapsed_ms,
                )

            with self._lock:
                current = self._inflight.get(name)
                if current is not None and current[0] is future:
                    self._inflight.pop(name, None)

        return result

    def close(self, *, wait_for_running: bool = False) -> None:
        self._executor.shutdown(wait=bool(wait_for_running), cancel_futures=True)
