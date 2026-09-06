from __future__ import annotations

import json
import math
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "trading_intelligence" / "learning_state.json"
MIN_SAMPLES_FOR_WEIGHT = 12
MAX_RECENT_OUTCOMES = 250


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _empty_bucket() -> dict[str, Any]:
    return {
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "breakeven": 0,
        "pnl": 0.0,
        "r_sum": 0.0,
        "r_count": 0,
        "weight": 1.0,
        "last_updated": None,
    }


def _default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "created_at": _now(),
        "updated_at": _now(),
        "families": {},
        "strategies": {},
        "regimes": {},
        "symbols": {},
        "mistakes": {},
        "recent_outcomes": [],
        "governance": {
            "minimum_samples_for_weight": MIN_SAMPLES_FOR_WEIGHT,
            "weight_floor": 0.85,
            "weight_ceiling": 1.15,
            "automatic_strategy_code_rewrite": False,
            "live_execution": False,
        },
    }


def _families_from_votes(votes: Iterable[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for vote in votes:
        family = str(vote.get("family") or "").strip().lower()
        if family and family not in result:
            result.append(family)
    return result


def _strategies_from_votes(votes: Iterable[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for vote in votes:
        strategy = str(vote.get("strategy") or "").strip().upper()
        if strategy and strategy not in result:
            result.append(strategy)
    return result


class TradeLearningEngine:
    """Persistent, bounded learning from paper-trade outcomes.

    The engine learns reliability priors for strategy families and records
    mistake hypotheses.  It does not rewrite production strategy code and it
    never enables broker execution.  Weight changes are bounded and require a
    minimum sample size so one trade cannot change behavior materially.
    """

    def __init__(self, state_path: Path | str | None = None) -> None:
        self.state_path = Path(state_path or os.getenv("JARVIS_TRADING_LEARNING_STATE", DEFAULT_STATE_PATH))
        self._lock = threading.RLock()
        self._state = self._load()

    @property
    def live_execution(self) -> bool:
        return False

    def _load(self) -> dict[str, Any]:
        try:
            if self.state_path.exists():
                value = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    base = _default_state()
                    base.update(value)
                    return base
        except Exception:
            pass
        return _default_state()

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._state, indent=2, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    @staticmethod
    def _bucket(table: dict[str, Any], key: str) -> dict[str, Any]:
        if key not in table or not isinstance(table.get(key), dict):
            table[key] = _empty_bucket()
        return table[key]

    @staticmethod
    def _update_bucket(bucket: dict[str, Any], pnl: float, r_multiple: float | None) -> None:
        bucket["trades"] = int(bucket.get("trades") or 0) + 1
        if pnl > 1e-9:
            bucket["wins"] = int(bucket.get("wins") or 0) + 1
        elif pnl < -1e-9:
            bucket["losses"] = int(bucket.get("losses") or 0) + 1
        else:
            bucket["breakeven"] = int(bucket.get("breakeven") or 0) + 1
        bucket["pnl"] = _f(bucket.get("pnl")) + pnl
        if r_multiple is not None and math.isfinite(float(r_multiple)):
            bucket["r_sum"] = _f(bucket.get("r_sum")) + float(r_multiple)
            bucket["r_count"] = int(bucket.get("r_count") or 0) + 1
        bucket["last_updated"] = _now()

    @staticmethod
    def _weight(bucket: dict[str, Any]) -> float:
        trades = int(bucket.get("trades") or 0)
        if trades < MIN_SAMPLES_FOR_WEIGHT:
            return 1.0
        wins = int(bucket.get("wins") or 0)
        r_count = int(bucket.get("r_count") or 0)
        posterior_win_rate = (wins + 2.0) / (trades + 4.0)
        avg_r = (_f(bucket.get("r_sum")) / r_count) if r_count else 0.0
        score = 1.0 + 0.28 * (posterior_win_rate - 0.5) + 0.10 * math.tanh(avg_r)
        return max(0.85, min(1.15, score))

    @staticmethod
    def _mistake_hypotheses(
        *,
        pnl: float,
        reason: str,
        metadata: dict[str, Any],
        entry: float,
        stop: float | None,
        target: float | None,
        score: float | None,
    ) -> list[str]:
        if pnl >= 0:
            return []
        mistakes: list[str] = []
        rr = metadata.get("risk_reward")
        if rr is not None and _f(rr) < 1.5:
            mistakes.append("LOW_INITIAL_RISK_REWARD")
        if score is not None and _f(score) < 70.0:
            mistakes.append("MARGINAL_SIGNAL_SCORE")
        if not metadata.get("regime"):
            mistakes.append("REGIME_CONTEXT_MISSING")
        votes = metadata.get("votes") if isinstance(metadata.get("votes"), list) else []
        long_votes = sum(1 for vote in votes if str(vote.get("side") or "").upper() == "LONG")
        short_votes = sum(1 for vote in votes if str(vote.get("side") or "").upper() == "SHORT")
        if long_votes and short_votes:
            dominant = max(long_votes, short_votes)
            minority = min(long_votes, short_votes)
            if minority / max(dominant, 1) >= 0.50:
                mistakes.append("HIGH_STRATEGY_DISAGREEMENT")
        if reason == "STOP_HIT":
            mistakes.append("STOP_HIT")
        if stop is None:
            mistakes.append("STOP_CONTEXT_MISSING")
        if target is None:
            mistakes.append("TARGET_CONTEXT_MISSING")
        if entry <= 0:
            mistakes.append("ENTRY_CONTEXT_INVALID")
        return mistakes

    def record_outcome(
        self,
        *,
        symbol: str,
        side: str,
        entry: float,
        exit_price: float,
        quantity: float,
        pnl: float,
        reason: str,
        metadata: dict[str, Any] | None = None,
        strategy: str | None = None,
        score: float | None = None,
        stop: float | None = None,
        target: float | None = None,
    ) -> dict[str, Any]:
        metadata = dict(metadata or {})
        risk_per_unit = abs(float(entry) - float(stop)) if stop is not None else 0.0
        total_initial_risk = risk_per_unit * abs(float(quantity))
        r_multiple = (float(pnl) / total_initial_risk) if total_initial_risk > 0 else None
        votes = metadata.get("votes") if isinstance(metadata.get("votes"), list) else []
        families = _families_from_votes(votes)
        strategies = _strategies_from_votes(votes)
        if strategy:
            normalized_strategy = str(strategy).strip().upper()
            if normalized_strategy and normalized_strategy not in strategies:
                strategies.append(normalized_strategy)
        regime = str(metadata.get("regime") or "UNKNOWN").upper()
        symbol = str(symbol or "UNKNOWN").upper()
        mistakes = self._mistake_hypotheses(
            pnl=float(pnl),
            reason=str(reason or ""),
            metadata=metadata,
            entry=float(entry),
            stop=float(stop) if stop is not None else None,
            target=float(target) if target is not None else None,
            score=float(score) if score is not None else None,
        )

        event = {
            "recorded_at": _now(),
            "symbol": symbol,
            "side": str(side or "").upper(),
            "entry": float(entry),
            "exit": float(exit_price),
            "quantity": float(quantity),
            "pnl": float(pnl),
            "r_multiple": r_multiple,
            "reason": str(reason or ""),
            "regime": regime,
            "families": families,
            "strategies": strategies,
            "score": float(score) if score is not None else None,
            "mistake_hypotheses": mistakes,
        }

        with self._lock:
            for family in families:
                bucket = self._bucket(self._state["families"], family)
                self._update_bucket(bucket, float(pnl), r_multiple)
                bucket["weight"] = self._weight(bucket)
            for strategy_name in strategies:
                bucket = self._bucket(self._state["strategies"], strategy_name)
                self._update_bucket(bucket, float(pnl), r_multiple)
                bucket["weight"] = self._weight(bucket)
            regime_bucket = self._bucket(self._state["regimes"], regime)
            self._update_bucket(regime_bucket, float(pnl), r_multiple)
            symbol_bucket = self._bucket(self._state["symbols"], symbol)
            self._update_bucket(symbol_bucket, float(pnl), r_multiple)
            for mistake in mistakes:
                self._state["mistakes"][mistake] = int(self._state["mistakes"].get(mistake) or 0) + 1
            recent = list(self._state.get("recent_outcomes") or [])
            recent.append(event)
            self._state["recent_outcomes"] = recent[-MAX_RECENT_OUTCOMES:]
            self._state["updated_at"] = _now()
            self._save()
        return {
            "success": True,
            "event": event,
            "family_weights": self.family_weights(),
            "paper_only": True,
            "live_execution": False,
        }

    def record_closed_row(self, row: Any, *, exit_price: float, pnl: float, reason: str) -> dict[str, Any]:
        def get(key: str, default: Any = None) -> Any:
            try:
                return row[key]
            except Exception:
                return default

        try:
            metadata = json.loads(get("metadata_json") or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}
        return self.record_outcome(
            symbol=str(get("symbol") or "UNKNOWN"),
            side=str(get("side") or ""),
            entry=_f(get("entry")),
            exit_price=float(exit_price),
            quantity=_f(get("quantity")),
            pnl=float(pnl),
            reason=str(reason or ""),
            metadata=metadata,
            strategy=str(get("strategy") or ""),
            score=_f(get("score")) if get("score") is not None else None,
            stop=_f(get("stop")) if get("stop") is not None else None,
            target=_f(get("target")) if get("target") is not None else None,
        )

    def family_weights(self) -> dict[str, float]:
        with self._lock:
            return {
                str(name): float(bucket.get("weight") or 1.0)
                for name, bucket in dict(self._state.get("families") or {}).items()
                if isinstance(bucket, dict)
            }

    def strategy_leaderboard(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._lock:
            source = deepcopy(self._state.get("strategies") or {})
        for name, bucket in source.items():
            if not isinstance(bucket, dict):
                continue
            trades = int(bucket.get("trades") or 0)
            wins = int(bucket.get("wins") or 0)
            r_count = int(bucket.get("r_count") or 0)
            rows.append(
                {
                    "strategy": name,
                    "trades": trades,
                    "wins": wins,
                    "losses": int(bucket.get("losses") or 0),
                    "win_rate": (wins / trades) if trades else None,
                    "pnl": _f(bucket.get("pnl")),
                    "avg_r": (_f(bucket.get("r_sum")) / r_count) if r_count else None,
                    "weight": _f(bucket.get("weight"), 1.0),
                    "eligible_for_weighting": trades >= MIN_SAMPLES_FOR_WEIGHT,
                }
            )
        rows.sort(key=lambda row: (row["weight"], row["avg_r"] or -999.0, row["trades"]), reverse=True)
        return rows

    def mistake_report(self) -> dict[str, Any]:
        with self._lock:
            mistakes = dict(self._state.get("mistakes") or {})
            recent = deepcopy(self._state.get("recent_outcomes") or [])
        ranked = sorted(mistakes.items(), key=lambda item: item[1], reverse=True)
        losses = [row for row in recent if _f(row.get("pnl")) < 0]
        return {
            "total_recorded_outcomes": len(recent),
            "recent_losses": losses[-20:],
            "ranked_mistakes": [{"mistake": name, "count": count} for name, count in ranked],
            "message": (
                "Mistakes are research hypotheses, not automatic code changes. "
                "JARVIS requires sufficient samples and out-of-sample validation before strategy promotion."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            value = deepcopy(self._state)
        value["family_weights"] = self.family_weights()
        value["strategy_leaderboard"] = self.strategy_leaderboard()[:25]
        value["paper_only"] = True
        value["live_execution"] = False
        return value


learning_engine = TradeLearningEngine()
