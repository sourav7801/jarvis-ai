from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "data" / "trading_intelligence" / "champion_challenger.json"
MAX_RECORDS = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChampionChallenger:
    """Compatibility comparator retained from the earlier research engine."""

    def compare(
        self,
        champion,
        challenger,
        *,
        minimum_margin=2.0,
    ):
        champion_score = float(champion["fitness"]["score"])
        challenger_score = float(challenger["fitness"]["score"])
        margin = challenger_score - champion_score
        if margin >= float(minimum_margin):
            decision = "RESEARCH_CHALLENGER_WINS"
        elif margin > 0:
            decision = "KEEP_TESTING"
        elif margin <= -10:
            decision = "CHALLENGER_DEGRADE"
        else:
            decision = "CHAMPION_RETAINS"
        return {
            "decision": decision,
            "champion_score": champion_score,
            "challenger_score": challenger_score,
            "margin": margin,
            "production_promotion": False,
            "registry_mutation": False,
            "research_only": True,
        }


class ChampionChallengerRegistry:
    """Persistent paper/research registry with no production promotion surface."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("records", [])
                value.setdefault("paper_champions", {})
                return value
        except (FileNotFoundError, OSError, ValueError):
            pass
        return {"version": 1, "records": [], "paper_champions": {}, "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _slot(symbol: str, timeframe: str, regime: str) -> str:
        return "|".join(
            [str(symbol or "UNKNOWN").upper(), str(timeframe or "UNKNOWN"), str(regime or "ANY").upper()]
        )

    def register(
        self,
        *,
        symbol: str,
        timeframe: str,
        regime: str,
        candidate: dict[str, Any],
        validation: dict[str, Any],
        source: str = "strategy_research_lab",
    ) -> dict[str, Any]:
        if not isinstance(candidate, dict) or not str(candidate.get("name") or "").strip():
            raise ValueError("A named strategy candidate is required.")
        if not isinstance(validation, dict):
            raise ValueError("Validation evidence is required.")
        eligible = bool(validation.get("passed"))
        record = {
            "record_id": "strategy-" + uuid4().hex[:16],
            "created_at": _now(),
            "symbol": str(symbol or "UNKNOWN").upper(),
            "timeframe": str(timeframe or "UNKNOWN"),
            "regime": str(regime or "ANY").upper(),
            "candidate": dict(candidate),
            "validation": dict(validation),
            "source": str(source or "")[:120],
            "status": "PAPER_CHALLENGER" if eligible else "RESEARCH_ONLY",
            "production_strategy_changed": False,
            "live_execution": False,
        }
        with self._lock:
            records = list(self._state.get("records") or [])
            records.append(record)
            self._state["records"] = records[-MAX_RECORDS:]
            self._state["updated_at"] = record["created_at"]
            self._save()
        return dict(record)

    def nominate_paper_champion(self, record_id: str) -> dict[str, Any]:
        """Nominate a robustly validated paper champion for one research slot."""

        value = str(record_id or "").strip()
        with self._lock:
            record = next(
                (item for item in self._state.get("records") or [] if item.get("record_id") == value),
                None,
            )
            if record is None:
                raise KeyError("Unknown strategy research record.")
            if record.get("status") != "PAPER_CHALLENGER" or not bool((record.get("validation") or {}).get("passed")):
                raise PermissionError("Only robustly validated paper challengers may become paper champions.")
            slot = self._slot(record["symbol"], record["timeframe"], record["regime"])
            champion = {
                "record_id": record["record_id"],
                "candidate": dict(record["candidate"]),
                "symbol": record["symbol"],
                "timeframe": record["timeframe"],
                "regime": record["regime"],
                "nominated_at": _now(),
                "scope": "PAPER_RESEARCH_ONLY",
            }
            self._state.setdefault("paper_champions", {})[slot] = champion
            record["status"] = "PAPER_CHAMPION"
            record["updated_at"] = champion["nominated_at"]
            self._state["updated_at"] = champion["nominated_at"]
            self._save()
            return dict(champion)

    def snapshot(self, *, limit: int = 100) -> dict[str, Any]:
        with self._lock:
            records = [dict(item) for item in self._state.get("records") or []]
            champions = dict(self._state.get("paper_champions") or {})
            updated = self._state.get("updated_at")
        counts: dict[str, int] = {}
        for record in records:
            status = str(record.get("status") or "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1
        return {
            "success": True,
            "version": "7.0",
            "updated_at": updated,
            "counts": counts,
            "paper_champions": champions,
            "records": records[-max(1, min(int(limit), MAX_RECORDS)):],
            "governance": {
                "automatic_production_promotion": False,
                "automatic_live_promotion": False,
                "production_code_rewrite": False,
                "paper_only": True,
            },
            "live_execution": False,
        }


champion_challenger = ChampionChallenger()
CHAMPION_CHALLENGER = ChampionChallengerRegistry()


__all__ = [
    "CHAMPION_CHALLENGER",
    "ChampionChallenger",
    "ChampionChallengerRegistry",
    "champion_challenger",
]
