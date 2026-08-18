"""Best-effort runtime audit facade used by the legacy-compatible entry point."""

from __future__ import annotations

import threading
from typing import Any

from config import AUDIT_DB, HYBRID_MEMORY_DB

from .audit import AuditStore


_store: AuditStore | None = None
_memory = None
_lock = threading.Lock()


def get_audit_store() -> AuditStore:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = AuditStore(AUDIT_DB)
    return _store


def get_memory_store():
    global _memory
    if _memory is None:
        with _lock:
            if _memory is None:
                from .hybrid_memory import HybridMemory

                _memory = HybridMemory(HYBRID_MEMORY_DB)
    return _memory


def audit_event(
    category: str,
    name: str,
    status: str,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> str | None:
    """Record telemetry without making audit availability a runtime outage."""
    try:
        return get_audit_store().record_event(
            category, name, status, payload, correlation_id
        )
    except Exception as error:
        print(f"JARVIS AUDIT DEBUG > {type(error).__name__}: {error}")
        return None
