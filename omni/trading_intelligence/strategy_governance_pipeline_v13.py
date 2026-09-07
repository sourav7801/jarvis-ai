from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "data" / "trading_intelligence" / "strategy_governance_v13.json"
MAX_RECORDS = 250
STAGES = (
    "RESEARCH_CANDIDATE",
    "VALIDATED",
    "CHALLENGER",
    "PAPER_SHADOW",
    "REVIEW",
    "CHAMPION",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrategyGovernancePipelineV13:
    """Persistent paper/research strategy lifecycle with explicit operator gate.

    CHAMPION means paper-research champion only. No stage change writes strategy
    source code, changes production configuration or enables live orders.
    """

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

    def register(
        self,
        *,
        name: str,
        symbol: str = "UNKNOWN",
        timeframe: str = "UNKNOWN",
        regime: str = "ANY",
        hypothesis: str = "",
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("strategy name required")
        record = {
            "record_id": "v13-strategy-" + uuid4().hex[:16],
            "name": clean_name[:160],
            "symbol": str(symbol or "UNKNOWN").upper()[:60],
            "timeframe": str(timeframe or "UNKNOWN")[:40],
            "regime": str(regime or "ANY").upper()[:60],
            "hypothesis": str(hypothesis or "")[:2000],
            "stage": "RESEARCH_CANDIDATE",
            "validation": None,
            "paper_shadow": None,
            "review": None,
            "operator_approved": False,
            "provenance": dict(provenance or {}),
            "created_at": _now(),
            "updated_at": _now(),
            "production_strategy_changed": False,
            "live_execution": False,
        }
        with self._lock:
            records = list(self._state.get("records") or [])
            records.append(record)
            self._state["records"] = records[-MAX_RECORDS:]
            self._state["updated_at"] = record["updated_at"]
            self._save()
        return dict(record)

    def _record(self, record_id: str) -> dict[str, Any]:
        record = next((item for item in self._state.get("records") or [] if item.get("record_id") == record_id), None)
        if record is None:
            raise KeyError("unknown strategy governance record")
        return record

    def mark_validated(self, record_id: str, validation: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(validation, Mapping):
            raise ValueError("validation evidence required")
        robust_passed = bool(validation.get("passed")) and bool(
            validation.get("out_of_sample_passed", validation.get("oos_passed", validation.get("passed")))
        )
        with self._lock:
            record = self._record(record_id)
            if record.get("stage") != "RESEARCH_CANDIDATE":
                raise PermissionError("validation is accepted only from RESEARCH_CANDIDATE")
            record["validation"] = dict(validation)
            if robust_passed:
                record["stage"] = "VALIDATED"
            record["updated_at"] = _now()
            self._state["updated_at"] = record["updated_at"]
            self._save()
            return dict(record)

    def advance(
        self,
        record_id: str,
        target_stage: str,
        *,
        evidence: Mapping[str, Any] | None = None,
        operator_approved: bool = False,
    ) -> dict[str, Any]:
        target = str(target_stage or "").strip().upper()
        if target not in STAGES:
            raise ValueError("unknown strategy governance stage")
        with self._lock:
            record = self._record(record_id)
            current = str(record.get("stage") or "RESEARCH_CANDIDATE")
            current_index = STAGES.index(current)
            target_index = STAGES.index(target)
            if target_index != current_index + 1:
                raise PermissionError("strategy stages must advance one governed step at a time")
            if current == "RESEARCH_CANDIDATE":
                raise PermissionError("use mark_validated() with robust validation evidence")
            if target == "CHAMPION" and not bool(operator_approved):
                raise PermissionError("operator approval is required for paper champion nomination")
            if target == "PAPER_SHADOW":
                record["paper_shadow"] = dict(evidence or {})
            elif target == "REVIEW":
                record["review"] = dict(evidence or {})
            record["stage"] = target
            record["operator_approved"] = bool(operator_approved) if target == "CHAMPION" else bool(record.get("operator_approved"))
            record["updated_at"] = _now()
            record["production_strategy_changed"] = False
            record["live_execution"] = False
            self._state["updated_at"] = record["updated_at"]
            self._save()
            return dict(record)

    def snapshot(self, *, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            records = [dict(item) for item in self._state.get("records") or []]
            updated = self._state.get("updated_at")
        counts = {stage: 0 for stage in STAGES}
        for item in records:
            stage = str(item.get("stage") or "")
            if stage in counts:
                counts[stage] += 1
        try:
            from omni.trading_intelligence.champion_challenger import CHAMPION_CHALLENGER
            legacy = CHAMPION_CHALLENGER.snapshot(limit=50)
        except Exception as exc:
            legacy = {"success": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        return {
            "success": True,
            "version": "13.0",
            "service": "JARVIS_STRATEGY_GOVERNANCE_PIPELINE_V13",
            "updated_at": updated,
            "stages": list(STAGES),
            "counts": counts,
            "records": records[-max(1, min(int(limit), MAX_RECORDS)):],
            "existing_champion_challenger": legacy,
            "governance": {
                "robust_validation_required": True,
                "paper_shadow_before_review": True,
                "operator_approval_required_for_champion": True,
                "champion_scope": "PAPER_RESEARCH_ONLY",
                "automatic_promotion": False,
                "automatic_production_strategy_rewrite": False,
                "automatic_live_promotion": False,
                "external_actions": "APPROVAL_GATED",
            },
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


STRATEGY_GOVERNANCE_PIPELINE_V13 = StrategyGovernancePipelineV13()

__all__ = ["STRATEGY_GOVERNANCE_PIPELINE_V13", "StrategyGovernancePipelineV13", "STAGES"]
