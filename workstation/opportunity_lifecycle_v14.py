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
MAX_ENGINE_REJECTIONS = 32
LIFECYCLE_VERSION = "OPPORTUNITY_LIFECYCLE_V14"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class OpportunityLifecycleV14:
    """Durable exact-state telemetry for autonomous paper opportunities.

    V14 never collapses every non-open case into WATCHING.  A symbol is marked
    as economically waiting, hard-blocked, actionable/recheck-pending, or opened.
    Engine-level execution rejection counts are stored separately so transient
    live-entry, cooldown, valuation, sizing or portfolio constraints remain
    visible even when the symbol-level evidence itself is actionable.
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
                value.setdefault("engine_rejections", {})
                return value
        except (OSError, ValueError):
            pass
        return {
            "version": "14.0",
            "active": {},
            "events": [],
            "engine_rejections": {},
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
    def _engine_key(bucket: str, lane: str | None) -> str:
        return f"{str(bucket or 'GENERAL').upper()}:{str(lane or 'BASE').upper()}"

    @staticmethod
    def _decision(row: Mapping[str, Any]) -> Mapping[str, Any]:
        decision = row.get("continuous_execution_decision")
        if isinstance(decision, Mapping):
            return decision
        decision = row.get("adaptive_decision")
        if isinstance(decision, Mapping):
            return decision
        return row

    @classmethod
    def _classify(cls, row: Mapping[str, Any]) -> tuple[str, str]:
        decision = cls._decision(row)
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

    def _row_record(
        self,
        row: Mapping[str, Any],
        *,
        bucket: str,
        lane: str | None,
        previous: Mapping[str, Any] | None,
        observed_at: str,
    ) -> dict[str, Any]:
        symbol = str(row.get("symbol") or "").strip().upper()
        state, reason = self._classify(row)
        decision = self._decision(row)
        return {
            "key": self._key(bucket, lane, symbol),
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

    @staticmethod
    def _opened_record(
        opened: Mapping[str, Any],
        *,
        bucket: str,
        lane: str | None,
        previous: Mapping[str, Any] | None,
        observed_at: str,
    ) -> dict[str, Any]:
        symbol = str(opened.get("symbol") or "").strip().upper()
        key = OpportunityLifecycleV14._key(bucket, lane, symbol)
        return {
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
        observed_at = _now()
        key = self._key(bucket, lane, symbol)
        with self._lock:
            active = dict(self._state.get("active") or {})
            previous = active.get(key) if isinstance(active.get(key), dict) else None
            record = self._row_record(
                row,
                bucket=bucket,
                lane=lane,
                previous=previous,
                observed_at=observed_at,
            )
            active[key] = record
            events = list(self._state.get("events") or [])
            if record["changed"]:
                events.append(record)
            self._state["active"] = active
            self._state["events"] = events[-MAX_EVENTS:]
            self._state["updated_at"] = observed_at
            self._trim_active()
            self._save()
        return dict(record)

    def _trim_active(self) -> None:
        active = dict(self._state.get("active") or {})
        if len(active) <= MAX_ACTIVE:
            return
        ordered = sorted(active.items(), key=lambda item: str(item[1].get("observed_at") or ""))
        self._state["active"] = dict(ordered[-MAX_ACTIVE:])

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
        observed_at = _now()
        key = self._key(bucket, lane, symbol)
        with self._lock:
            active = dict(self._state.get("active") or {})
            previous = active.get(key) if isinstance(active.get(key), dict) else None
            record = self._opened_record(
                opened,
                bucket=bucket,
                lane=lane,
                previous=previous,
                observed_at=observed_at,
            )
            active[key] = record
            events = list(self._state.get("events") or [])
            events.append(record)
            self._state["active"] = active
            self._state["events"] = events[-MAX_EVENTS:]
            self._state["updated_at"] = observed_at
            self._trim_active()
            self._save()
        return dict(record)

    def observe_engine(self, engine: Any, result: Mapping[str, Any] | None = None) -> dict[str, Any]:
        try:
            status = engine.status()
        except Exception as exc:
            return {"success": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
        bucket = str(status.get("portfolio_bucket") or "GENERAL").upper()
        lane = str(status.get("profile") or "BASE")
        rows = [row for row in list(status.get("last_rows_summary") or []) if isinstance(row, Mapping)]
        opened_rows = [row for row in list((result or {}).get("opened") or []) if isinstance(row, Mapping)]
        rejection_counts = (
            dict((result or {}).get("rejection_counts") or {})
            if isinstance((result or {}).get("rejection_counts"), Mapping)
            else dict(status.get("last_rejection_counts") or {})
            if isinstance(status.get("last_rejection_counts"), Mapping)
            else {}
        )
        observed_at = _now()
        records: list[dict[str, Any]] = []
        with self._lock:
            active = dict(self._state.get("active") or {})
            events = list(self._state.get("events") or [])
            for row in rows:
                symbol = str(row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                key = self._key(bucket, lane, symbol)
                previous = active.get(key) if isinstance(active.get(key), dict) else None
                record = self._row_record(
                    row,
                    bucket=bucket,
                    lane=lane,
                    previous=previous,
                    observed_at=observed_at,
                )
                active[key] = record
                records.append(record)
                if record["changed"]:
                    events.append(record)
            for opened in opened_rows:
                symbol = str(opened.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                key = self._key(bucket, lane, symbol)
                previous = active.get(key) if isinstance(active.get(key), dict) else None
                record = self._opened_record(
                    opened,
                    bucket=bucket,
                    lane=lane,
                    previous=previous,
                    observed_at=observed_at,
                )
                active[key] = record
                records.append(record)
                events.append(record)

            engine_rejections = dict(self._state.get("engine_rejections") or {})
            engine_key = self._engine_key(bucket, lane)
            engine_rejections[engine_key] = {
                "bucket": bucket,
                "lane": lane,
                "counts": {str(key): int(value) for key, value in rejection_counts.items() if int(value) > 0},
                "observed_at": observed_at,
            }
            if len(engine_rejections) > MAX_ENGINE_REJECTIONS:
                ordered = sorted(
                    engine_rejections.items(),
                    key=lambda item: str(item[1].get("observed_at") or ""),
                )
                engine_rejections = dict(ordered[-MAX_ENGINE_REJECTIONS:])

            self._state["active"] = active
            self._state["events"] = events[-MAX_EVENTS:]
            self._state["engine_rejections"] = engine_rejections
            self._state["updated_at"] = observed_at
            self._trim_active()
            self._save()
        return {
            "success": True,
            "observed": len(records),
            "bucket": bucket,
            "lane": lane,
            "execution_rejection_counts": rejection_counts,
            "paper_only": True,
            "live_execution": False,
        }

    def snapshot(self, *, limit: int = 120) -> dict[str, Any]:
        with self._lock:
            active = [dict(value) for value in (self._state.get("active") or {}).values() if isinstance(value, dict)]
            events = [dict(value) for value in list(self._state.get("events") or []) if isinstance(value, dict)]
            engine_rejections = [
                dict(value)
                for value in (self._state.get("engine_rejections") or {}).values()
                if isinstance(value, dict)
            ]
            updated = self._state.get("updated_at")
        active.sort(key=lambda row: str(row.get("observed_at") or ""), reverse=True)
        counts: dict[str, int] = {}
        hard_blockers: dict[str, int] = {}
        for row in active:
            state = str(row.get("state") or "UNKNOWN")
            counts[state] = counts.get(state, 0) + 1
            for blocker in list(row.get("hard_blockers") or []):
                token = str(blocker)
                hard_blockers[token] = hard_blockers.get(token, 0) + 1
        execution_rejections: dict[str, int] = {}
        for engine in engine_rejections:
            table = engine.get("counts") if isinstance(engine.get("counts"), Mapping) else {}
            for reason, count in table.items():
                execution_rejections[str(reason)] = execution_rejections.get(str(reason), 0) + int(count)
        top_hard = sorted(hard_blockers.items(), key=lambda item: item[1], reverse=True)[:12]
        top_execution = sorted(execution_rejections.items(), key=lambda item: item[1], reverse=True)[:12]
        return {
            "success": True,
            "version": "14.0",
            "service": LIFECYCLE_VERSION,
            "updated_at": updated,
            "active_count": len(active),
            "state_counts": counts,
            "top_hard_blockers": [{"reason": reason, "count": count} for reason, count in top_hard],
            "top_execution_rejections": [{"reason": reason, "count": count} for reason, count in top_execution],
            "engine_rejections": engine_rejections,
            "active": active[: max(1, min(int(limit), MAX_ACTIVE))],
            "recent_events": events[-max(1, min(int(limit), MAX_EVENTS)):][::-1],
            "watching_is_not_a_terminal_state": True,
            "engine_execution_rejections_are_explicit": True,
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
