from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "trading_intelligence" / "opportunity_lifecycle_v14.json"
MAX_EVENTS = 600
MAX_ACTIVE = 160
LIFECYCLE_VERSION = "OPPORTUNITY_LIFECYCLE_V14"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class OpportunityLifecycleV14:
    """Durable explanation layer for autonomous paper opportunity states.

    The lifecycle does not manufacture trades.  It records whether each symbol
    is waiting because EV is non-positive, blocked by real safety/data, is
    actionable but awaiting the next execution attempt, or actually opened.
    This removes the ambiguous all-purpose WATCHING state from V14 telemetry.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("active", {})
                value.setdefault("events", [])
                return value
        except (OSError, ValueError):
            pass
        return {
            "version": "14.0",
            "active": {},
            "events": [],
            "updated_at": None,
        }

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _key(bucket: str, lane: str | None, symbol: str) -> str:
        return ":".join(
            [
                str(bucket or "GENERAL").upper(),
                str(lane or "BASE").upper(),
                str(symbol or "UNKNOWN").upper(),
            ]
        )

    @staticmethod
    def _classify(row: Mapping[str, Any]) -> tuple[str, str]:
        decision = row.get("continuous_execution_decision")
        if not isinstance(decision, Mapping):
            decision = row.get("adaptive_decision") if isinstance(row.get("adaptive_decision"), Mapping) else row
        hard = [str(item) for item in list(decision.get("hard_blockers") or row.get("hard_blockers") or [])]
        executable = decision.get("executable") is True or row.get("adaptive_executable") is True
        ev = _f(decision.get("expected_value_r", row.get("adaptive_expected_value_r")))
        if hard:
            return "BLOCKED_SAFETY_OR_DATA", hard[0]
        if executable:
            return "ACTIONABLE", "POSITIVE_CONTEXTUAL_EV"
        if ev <= 0.0:
            return "WAIT_NEGATIVE_OR_ZERO_EV", "NON_POSITIVE_CONTEXTUAL_EV"
        return "RECHECK_PENDING", "POSITIVE_EV_PENDING_EXECUTION_RECHECK"

    def observe_row(
        self,
        row: Mapping[str, Any],
        *,
        bucket: str,
        lane: str | None = None,
    ) -> dict[str, Any]:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            return {"success": False, "reason": "SYMBOL_REQUIRED"}
        state, reason = self._classify(row)
        decision = row.get("continuous_execution_decision")
        if not isinstance(decision, Mapping):
            decision = row.get("adaptive_decision") if isinstance(row.get("adaptive_decision"), Mapping) else {}
        key = self._key(bucket, lane, symbol)
        observed_at = _now()
        with self._lock:
            active = dict(self._state.get("active") or {})
            previous = active.get(key) if isinstance(active.get(key), dict) else None
            record = {
                "key": key,
                "symbol": symbol,
                "bucket": str(bucket or "GENERAL").upper(),
                "lane": str(lane or "BASE").upper(),
                "state": state,
                "reason": reason,
                "previous_state": previous.get("state") if previous else None,
                "changed": previous is None or previous.get("state") != state or previous.get("reason") != reason,
                "expected_value_r": decision.get("expected_value_r", row.get("adaptive_expected_value_r")),
                "confidence": decision.get("confidence", row.get("adaptive_confidence")),
                "risk_multiplier": decision.get("risk_multiplier", row.get("adaptive_risk_multiplier")),
                "action": decision.get("action", row.get("adaptive_action")),
                "legacy_score": row.get("legacy_score", row.get("score", row.get("execution_score"))),
                "hard_blockers": list(decision.get("hard_blockers") or row.get("hard_blockers") or []),
                "soft_evidence": list(decision.get("soft_evidence") or row.get("soft_evidence") or []),
                "observed_at": observed_at,
                "paper_only": True,
                "live_execution": False,
            }
            active[key] = record
            if len(active) > MAX_ACTIVE:
                ordered = sorted(active.items(), key=lambda item: str(item[1].get("observed_at") or ""))
                active = dict(ordered[-MAX_ACTIVE:])
            events = list(self._state.get("events") or [])
            if record["changed"]:
                events.append(record)
            self._state["active"] = active
            self._state["events"] = events[-MAX_EVENTS:]
            self._state["updated_at"] = observed_at
            self._save()
        return dict(record)

    def record_opened(
        self,
        opened: Mapping[str, Any],
        *,
        bucket: str,
        lane: str | None = None,
    ) -> dict[str, Any]:
        symbol = str(opened.get("symbol") or "").strip().upper()
        if not symbol:
            return {"success": False, "reason": "SYMBOL_REQUIRED"}
        key = self._key(bucket, lane, symbol)
        observed_at = _now()
        with self._lock:
            active = dict(self._state.get("active") or {})
            previous = active.get(key) if isinstance(active.get(key), dict) else None
            record = {
                "key": key,
                "symbol": symbol,
                "bucket": str(bucket or "GENERAL").upper(),
                "lane": str(lane or "BASE").upper(),
                "state": "POSITION_OPENED",
                "reason": str(opened.get("reason") or "PAPER_POSITION_OPENED"),
                "previous_state": previous.get("state") if previous else None,
                "changed": True,
                "position_id": opened.get("position_id"),
                "quantity": opened.get("quantity"),
                "side": opened.get("side"),
                "entry": opened.get("entry"),
                "stop": opened.get("stop"),
                "target": opened.get("target"),
                "sizing": opened.get("sizing"),
                "observed_at": observed_at,
                "paper_only": True,
                "live_execution": False,
            }
            active[key] = record
            events = list(self._state.get("events") or [])
            events.append(record)
            self._state["active"] = active
            self._state["events"] = events[-MAX_EVENTS:]
            self._state["updated_at"] = observed_at
            self._save()
        return dict(record)

    def observe_engine(self, engine: Any, result: Mapping[str, Any] | None = None) -> dict[str, Any]:
        try:
            status = engine.status()
        except Exception as exc:
            return {"success": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
        bucket = str(status.get("portfolio_bucket") or "GENERAL").upper()
        lane = status.get("profile")
        rows = [row for row in list(status.get("last_rows_summary") or []) if isinstance(row, Mapping)]
        records = [self.observe_row(row, bucket=bucket, lane=str(lane or "BASE")) for row in rows]
        for opened in list((result or {}).get("opened") or []):
            if isinstance(opened, Mapping):
                records.append(self.record_opened(opened, bucket=bucket, lane=str(lane or "BASE")))
        return {
            "success": True,
            "observed": len(records),
            "bucket": bucket,
            "lane": lane,
            "paper_only": True,
            "live_execution": False,
        }

    def snapshot(self, *, limit: int = 120) -> dict[str, Any]:
        with self._lock:
            active = [dict(value) for value in (self._state.get("active") or {}).values() if isinstance(value, dict)]
            events = [dict(value) for value in list(self._state.get("events") or []) if isinstance(value, dict)]
            updated = self._state.get("updated_at")
        active.sort(key=lambda row: str(row.get("observed_at") or ""), reverse=True)
        counts: dict[str, int] = {}
        for row in active:
            state = str(row.get("state") or "UNKNOWN")
            counts[state] = counts.get(state, 0) + 1
        blockers: dict[str, int] = {}
        for row in active:
            for blocker in list(row.get("hard_blockers") or []):
                token = str(blocker)
                blockers[token] = blockers.get(token, 0) + 1
        top_blockers = sorted(blockers.items(), key=lambda item: item[1], reverse=True)[:12]
        return {
            "success": True,
            "version": "14.0",
            "service": LIFECYCLE_VERSION,
            "updated_at": updated,
            "active_count": len(active),
            "state_counts": counts,
            "top_hard_blockers": [
                {"reason": reason, "count": count} for reason, count in top_blockers
            ],
            "active": active[: max(1, min(int(limit), MAX_ACTIVE))],
            "recent_events": events[-max(1, min(int(limit), MAX_EVENTS)):][::-1],
            "watching_is_not_a_terminal_state": True,
            "states": [
                "WAIT_NEGATIVE_OR_ZERO_EV",
                "BLOCKED_SAFETY_OR_DATA",
                "RECHECK_PENDING",
                "ACTIONABLE",
                "POSITION_OPENED",
            ],
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


OPPORTUNITY_LIFECYCLE_V14 = OpportunityLifecycleV14()

__all__ = ["OPPORTUNITY_LIFECYCLE_V14", "OpportunityLifecycleV14", "LIFECYCLE_VERSION"]
