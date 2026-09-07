"""Bounded persistent evidence/provenance ledger for JARVIS V10.

The ledger stores local reasoning evidence only. It never executes tools, places
orders, contacts external parties, or grants approval. Sensitive-looking fields
are redacted before persistence.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "state" / "evidence_ledger.json"
MAX_RECORDS = 1200
_SENSITIVE = (
    "authorization", "api_key", "apikey", "token", "secret", "password",
    "cookie", "credential", "access_key", "refresh_key", "app_secret",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sensitive_key(value: Any) -> bool:
    key = str(value or "").strip().lower().replace("-", "_")
    return any(part in key for part in _SENSITIVE)


def _bounded(value: Any, depth: int = 0) -> Any:
    if depth >= 4:
        return str(value)[:1200]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:2400]
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:60]:
            clean = str(key)[:120]
            output[clean] = "[REDACTED]" if _sensitive_key(clean) else _bounded(item, depth + 1)
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_bounded(item, depth + 1) for item in list(value)[:60]]
    return str(value)[:2400]


class EvidenceLedger:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("records", [])
                return value
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass
        return {"version": 1, "records": [], "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def record(
        self,
        *,
        kind: str,
        subject: str,
        claim: str,
        source: str,
        state: str = "OBSERVED",
        confidence: float = 1.0,
        evidence: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        freshness: str | None = None,
    ) -> dict[str, Any]:
        if not str(subject or "").strip() or not str(source or "").strip():
            raise ValueError("Evidence requires subject and source.")
        record = {
            "evidence_id": "evidence-" + uuid4().hex[:20],
            "kind": str(kind or "GENERAL").strip().upper()[:100],
            "subject": str(subject or "").strip()[:240],
            "claim": str(claim or "").strip()[:3000],
            "source": str(source or "").strip()[:240],
            "state": str(state or "OBSERVED").strip().upper()[:80],
            "confidence": round(max(0.0, min(float(confidence), 1.0)), 4),
            "freshness": str(freshness or "UNKNOWN").strip().upper()[:80],
            "evidence": _bounded(dict(evidence or {})),
            "provenance": _bounded(dict(provenance or {})),
            "correlation_id": str(correlation_id or "").strip()[:160] or None,
            "recorded_at": _now(),
        }
        with self._lock:
            rows = list(self._state.get("records") or [])
            rows.append(record)
            self._state["records"] = rows[-MAX_RECORDS:]
            self._state["updated_at"] = record["recorded_at"]
            self._save()
        return dict(record)

    def snapshot(
        self,
        *,
        limit: int = 100,
        kind: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), MAX_RECORDS))
        with self._lock:
            rows = [dict(item) for item in self._state.get("records") or []]
            updated_at = self._state.get("updated_at")
        if kind:
            normalized = str(kind).strip().upper()
            rows = [row for row in rows if row.get("kind") == normalized]
        if correlation_id:
            rows = [row for row in rows if row.get("correlation_id") == str(correlation_id)]
        return {
            "success": True,
            "version": "10.0",
            "updated_at": updated_at,
            "count": len(rows),
            "records": rows[-limit:],
            "bounded": True,
            "redacts_sensitive_fields": True,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


EVIDENCE_LEDGER = EvidenceLedger()

__all__ = ["EVIDENCE_LEDGER", "EvidenceLedger"]
