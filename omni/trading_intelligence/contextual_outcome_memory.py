from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


MEMORY_VERSION = "CONTEXTUAL_OUTCOME_MEMORY_V13"
MAX_CLOSED_TRADES = 200
CACHE_SECONDS = 30.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _token(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or "").strip().upper()
    return text or default


def _timeframe_from_trade(trade: Mapping[str, Any]) -> str:
    metadata = trade.get("metadata") if isinstance(trade.get("metadata"), Mapping) else {}
    return _token(trade.get("timeframe") or metadata.get("profile") or metadata.get("portfolio_bucket"))


def _setup_from_metadata(metadata: Mapping[str, Any]) -> str:
    pattern = metadata.get("pattern_confirmation")
    if isinstance(pattern, Mapping):
        state = _token(pattern.get("state"), "")
        if state:
            return state
    return _token(metadata.get("setup_type") or metadata.get("strategy_family") or metadata.get("strategy"), "ANY")


def _trade_context(trade: Mapping[str, Any]) -> dict[str, str]:
    metadata = trade.get("metadata") if isinstance(trade.get("metadata"), Mapping) else {}
    return {
        "symbol": _token(trade.get("symbol")),
        "timeframe": _timeframe_from_trade(trade),
        "regime": _token(metadata.get("regime"), "ANY"),
        "action": _token(metadata.get("adaptive_action"), "ANY"),
        "side": _token(trade.get("side"), "ANY"),
        "setup": _setup_from_metadata(metadata),
    }


def _row_context(row: Mapping[str, Any], action: str | None = None) -> dict[str, str]:
    pattern = row.get("pattern_confirmation")
    setup = "ANY"
    if isinstance(pattern, Mapping):
        setup = _token(pattern.get("state"), "ANY")
    timeframe = row.get("timeframe") or row.get("profile")
    return {
        "symbol": _token(row.get("symbol")),
        "timeframe": _token(timeframe),
        "regime": _token(row.get("regime"), "ANY"),
        "action": _token(action or ((row.get("adaptive_decision") or {}).get("action") if isinstance(row.get("adaptive_decision"), Mapping) else None), "ANY"),
        "side": _token(row.get("candidate_side") or row.get("side"), "ANY"),
        "setup": setup,
    }


def _realized_r(trade: Mapping[str, Any]) -> float | None:
    for key in ("realized_r", "realized_r_multiple", "r_multiple"):
        if trade.get(key) is not None:
            return _f(trade.get(key))
    entry = _f(trade.get("entry"))
    stop = _f(trade.get("stop"))
    pnl = trade.get("realized_pnl")
    quantity = abs(_f(trade.get("quantity")))
    initial_risk = abs(entry - stop) * quantity
    if pnl is None or initial_risk <= 0:
        return None
    return _f(pnl) / initial_risk


def _summary(values: Iterable[float]) -> dict[str, Any]:
    data = [float(value) for value in values if math.isfinite(float(value))]
    count = len(data)
    wins = sum(1 for value in data if value > 0)
    losses = sum(1 for value in data if value < 0)
    alpha = 2.0 + wins
    beta = 2.0 + losses
    posterior_win_rate = alpha / (alpha + beta)
    mean_r = sum(data) / count if count else 0.0
    # Shrink tiny samples aggressively toward a neutral zero-R prior.
    weight = count / (count + 10.0)
    posterior_mean_r = mean_r * weight
    confidence = min(0.90, count / (count + 18.0))
    return {
        "sample_count": count,
        "wins": wins,
        "losses": losses,
        "posterior_win_rate": round(posterior_win_rate, 4),
        "mean_r": round(mean_r, 4),
        "posterior_mean_r": round(posterior_mean_r, 4),
        "confidence": round(confidence, 4),
    }


class ContextualOutcomeMemory:
    """Bounded read-through memory derived only from durable closed paper trades.

    No synthetic history is created. Small cohorts are Bayesian/shrinkage weighted
    so a handful of outcomes cannot dominate V13 decisions.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache_at = 0.0
        self._cache: dict[str, Any] | None = None

    @staticmethod
    def _closed_trades() -> list[dict[str, Any]]:
        from workstation.paper_trading_desk import paper_desk

        return [dict(item) for item in list(paper_desk.closed_positions(MAX_CLOSED_TRADES))]

    def _build(self) -> dict[str, Any]:
        trades = self._closed_trades()
        buckets: dict[str, list[float]] = defaultdict(list)
        usable = 0
        for trade in trades:
            realized = _realized_r(trade)
            if realized is None or not math.isfinite(realized):
                continue
            usable += 1
            ctx = _trade_context(trade)
            buckets["GLOBAL"].append(realized)
            for dimension in ("symbol", "timeframe", "regime", "action", "side", "setup"):
                buckets[f"{dimension}:{ctx[dimension]}"] .append(realized)
            composite = "|".join(ctx[key] for key in ("symbol", "timeframe", "regime", "side", "setup"))
            buckets[f"context:{composite}"].append(realized)

        summaries = {key: _summary(values) for key, values in buckets.items()}
        return {
            "success": True,
            "version": MEMORY_VERSION,
            "generated_at": _now(),
            "closed_trade_count": len(trades),
            "usable_r_count": usable,
            "cohort_count": len(summaries),
            "cohorts": summaries,
            "source": "PAPER_DESK_CLOSED_POSITIONS",
            "synthetic_history": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_production_strategy_rewrite": False,
        }

    def snapshot(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            if not force and self._cache is not None and now - self._cache_at < CACHE_SECONDS:
                return dict(self._cache)
            payload = self._build()
            self._cache = payload
            self._cache_at = now
            return dict(payload)

    def lookup(self, row: Mapping[str, Any], *, action: str | None = None) -> dict[str, Any]:
        state = self.snapshot()
        cohorts = state.get("cohorts") if isinstance(state.get("cohorts"), Mapping) else {}
        ctx = _row_context(row, action)
        keys = [
            "GLOBAL",
            f"symbol:{ctx['symbol']}",
            f"timeframe:{ctx['timeframe']}",
            f"regime:{ctx['regime']}",
            f"action:{ctx['action']}",
            f"side:{ctx['side']}",
            f"setup:{ctx['setup']}",
            "context:" + "|".join(ctx[key] for key in ("symbol", "timeframe", "regime", "side", "setup")),
        ]
        rows = []
        weighted_edge = 0.0
        weighted_win = 0.0
        total_weight = 0.0
        for rank, key in enumerate(keys):
            summary = cohorts.get(key)
            if not isinstance(summary, Mapping) or int(summary.get("sample_count") or 0) <= 0:
                continue
            specificity = 0.35 + 0.65 * (rank / max(len(keys) - 1, 1))
            confidence = _f(summary.get("confidence"))
            weight = max(0.01, specificity * confidence)
            weighted_edge += _f(summary.get("posterior_mean_r")) * weight
            weighted_win += _f(summary.get("posterior_win_rate"), 0.5) * weight
            total_weight += weight
            rows.append({"key": key, **dict(summary), "weight": round(weight, 4)})
        return {
            "success": True,
            "version": MEMORY_VERSION,
            "context": ctx,
            "matched_cohorts": rows,
            "matched_count": len(rows),
            "posterior_edge_r": round(weighted_edge / total_weight, 4) if total_weight else 0.0,
            "posterior_win_rate": round(weighted_win / total_weight, 4) if total_weight else 0.5,
            "confidence": round(min(0.90, total_weight / (total_weight + 1.5)), 4) if total_weight else 0.0,
            "evidence_available": bool(rows),
            "source": "PAPER_DESK_CLOSED_POSITIONS",
            "synthetic_history": False,
            "paper_only": True,
            "live_execution": False,
        }


CONTEXTUAL_OUTCOME_MEMORY = ContextualOutcomeMemory()

__all__ = ["CONTEXTUAL_OUTCOME_MEMORY", "ContextualOutcomeMemory", "MEMORY_VERSION"]
