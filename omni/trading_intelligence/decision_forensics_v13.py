from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "data" / "trading_intelligence" / "v13_decision_forensics.json"
MAX_RECORDS = 400


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return str(value)[:300]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            name = str(key)
            if any(token in name.lower() for token in ("secret", "token", "password", "authorization", "cookie")):
                result[name] = "<REDACTED>"
            else:
                result[name] = _safe(item, depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_safe(item, depth + 1) for item in list(value)[:100]]
    return str(value)[:500]


class DecisionForensicsV13:
    """Bounded local evidence trail explaining why V13 acted or waited."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("records", [])
                return payload
        except (FileNotFoundError, OSError, ValueError):
            pass
        return {"version": "13.0", "records": [], "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, indent=2, sort_keys=True, default=str), encoding="utf-8")
        temporary.replace(self.path)

    def record(
        self,
        *,
        row: Mapping[str, Any],
        decision: Mapping[str, Any],
        correlation: Mapping[str, Any] | None = None,
        phase: str = "SCAN",
    ) -> dict[str, Any]:
        base = decision.get("base_v12_decision") if isinstance(decision.get("base_v12_decision"), Mapping) else {}
        memory = decision.get("contextual_memory") if isinstance(decision.get("contextual_memory"), Mapping) else {}
        correlation_payload = dict(correlation or {})
        record = {
            "recorded_at": _now(),
            "phase": str(phase or "SCAN")[:40],
            "symbol": str(row.get("symbol") or "").upper(),
            "profile": row.get("profile"),
            "timeframe": row.get("timeframe"),
            "candidate_side": row.get("candidate_side"),
            "legacy_score": row.get("score"),
            "legacy_qualified": row.get("qualified"),
            "base_v12_action": base.get("action"),
            "base_v12_ev_r": base.get("expected_value_r"),
            "final_action": decision.get("action"),
            "final_ev_r": decision.get("expected_value_r"),
            "final_confidence": decision.get("confidence"),
            "final_uncertainty": decision.get("uncertainty"),
            "dynamic_hurdle_r": decision.get("required_edge_r"),
            "context_edge_r": memory.get("posterior_edge_r"),
            "context_win_rate": memory.get("posterior_win_rate"),
            "context_confidence": memory.get("confidence"),
            "correlation_state": correlation_payload.get("state"),
            "correlation_multiplier": correlation_payload.get("risk_multiplier"),
            "hard_blockers": list(decision.get("hard_blockers") or [])[:30],
            "soft_evidence": list(decision.get("soft_evidence") or [])[:30],
            "reasons": list(decision.get("reasons") or [])[:30],
            "entry": row.get("entry"),
            "stop": row.get("stop"),
            "target": row.get("target"),
            "risk_reward": row.get("risk_reward"),
            "regime": row.get("regime"),
            "source": row.get("source") or row.get("provider"),
            "paper_only": True,
            "live_execution": False,
        }
        record = _safe(record)
        with self._lock:
            records = list(self._state.get("records") or [])
            previous = next(
                (item for item in reversed(records) if item.get("symbol") == record.get("symbol") and item.get("profile") == record.get("profile")),
                None,
            )
            if previous:
                record["changed_since_previous"] = {
                    "action": [previous.get("final_action"), record.get("final_action")],
                    "ev_r": [previous.get("final_ev_r"), record.get("final_ev_r")],
                    "confidence": [previous.get("final_confidence"), record.get("final_confidence")],
                    "hard_blockers": [previous.get("hard_blockers") or [], record.get("hard_blockers") or []],
                }
            records.append(record)
            self._state["records"] = records[-MAX_RECORDS:]
            self._state["updated_at"] = record["recorded_at"]
            self._save()
        return dict(record)

    def snapshot(self, *, symbol: str | None = None, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            records = [dict(item) for item in self._state.get("records") or []]
            updated = self._state.get("updated_at")
        if symbol:
            normalized = str(symbol).strip().upper()
            records = [item for item in records if str(item.get("symbol") or "").upper() == normalized]
        selected = records[-max(1, min(int(limit), MAX_RECORDS)):]
        return {
            "success": True,
            "version": "13.0",
            "service": "JARVIS_DECISION_FORENSICS_V13",
            "updated_at": updated,
            "record_count": len(records),
            "records": selected,
            "bounded": True,
            "max_records": MAX_RECORDS,
            "sensitive_fields_redacted": True,
            "paper_only": True,
            "live_execution": False,
        }


DECISION_FORENSICS_V13 = DecisionForensicsV13()

__all__ = ["DECISION_FORENSICS_V13", "DecisionForensicsV13"]
