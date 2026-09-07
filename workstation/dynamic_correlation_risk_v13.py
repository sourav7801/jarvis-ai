from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Mapping


CORRELATION_VERSION = "DYNAMIC_CORRELATION_RISK_V13"
MIN_OBSERVATIONS = 30
MAX_OPEN_COMPARISONS = 8
CACHE_SECONDS = 30.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _time_key(row: Mapping[str, Any], index: int) -> Any:
    for key in ("timestamp", "time", "ts", "epoch", "datetime"):
        if row.get(key) is not None:
            return row.get(key)
    return index


def _returns(candles: list[dict[str, Any]]) -> dict[Any, float]:
    result: dict[Any, float] = {}
    previous: float | None = None
    for index, row in enumerate(candles):
        close = _f(row.get("close"), float("nan"))
        if not math.isfinite(close) or close <= 0:
            previous = None
            continue
        if previous is not None and previous > 0:
            result[_time_key(row, index)] = (close / previous) - 1.0
        previous = close
    return result


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < MIN_OBSERVATIONS:
        return None
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    left_var = sum((a - mean_left) ** 2 for a in left)
    right_var = sum((b - mean_right) ** 2 for b in right)
    denominator = math.sqrt(left_var * right_var)
    if denominator <= 0:
        return None
    return max(-1.0, min(1.0, covariance / denominator))


def _profile_timeframe(profile: str | None, row_timeframe: str | None = None) -> str:
    value = str(row_timeframe or "").strip().lower()
    for token in ("5m", "10m", "15m", "30m", "1h", "2h", "4h", "1d"):
        if value == token:
            return "5m" if token == "10m" else token
    profile_value = str(profile or "").strip().lower()
    if "investment" in profile_value:
        return "1d"
    if "swing" in profile_value:
        return "1h"
    return "15m"


class DynamicCorrelationRiskV13:
    """Completed-bar, evidence-only portfolio correlation overlay.

    Correlation can reduce paper risk but never invents a relationship when
    aligned data is missing. The durable Paper Desk remains the final portfolio
    risk authority. This layer cannot increase risk above the base decision.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    def _series(self, symbol: str, timeframe: str) -> dict[str, Any]:
        key = (str(symbol).upper(), timeframe)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < CACHE_SECONDS:
                return dict(cached[1])
        from workstation.quant_terminal_v2 import candles_payload, completed_candles

        payload = candles_payload(key[0], timeframe, 180)
        raw = list(payload.get("candles") or []) if isinstance(payload, Mapping) else []
        completed = completed_candles(raw, timeframe)
        result = {
            "success": bool(payload.get("success")) and len(completed) >= MIN_OBSERVATIONS + 1,
            "symbol": key[0],
            "timeframe": timeframe,
            "source": payload.get("source") or payload.get("provider"),
            "completed_bar_count": len(completed),
            "returns": _returns([dict(item) for item in completed if isinstance(item, Mapping)]),
            "forming_bar_excluded": len(completed) < len(raw),
        }
        with self._lock:
            self._cache[key] = (now, result)
        return dict(result)

    @staticmethod
    def _pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[float | None, int]:
        a = left.get("returns") if isinstance(left.get("returns"), Mapping) else {}
        b = right.get("returns") if isinstance(right.get("returns"), Mapping) else {}
        common = [key for key in a if key in b]
        if len(common) < MIN_OBSERVATIONS:
            return None, len(common)
        correlation = _pearson([_f(a[key]) for key in common], [_f(b[key]) for key in common])
        return correlation, len(common)

    def assess(
        self,
        *,
        symbol: str,
        side: str,
        profile: str | None = None,
        timeframe: str | None = None,
        positions: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        normalized_side = str(side or "").strip().upper()
        tf = _profile_timeframe(profile, timeframe)
        if positions is None:
            from workstation.paper_trading_desk import paper_desk

            positions = list(paper_desk.snapshot().get("positions") or [])
        peers = [
            dict(item)
            for item in positions
            if isinstance(item, Mapping)
            and str(item.get("symbol") or "").strip().upper()
            and str(item.get("symbol") or "").strip().upper() != normalized_symbol
        ][:MAX_OPEN_COMPARISONS]

        if not normalized_symbol or normalized_side not in {"LONG", "SHORT"}:
            return {
                "success": False,
                "version": CORRELATION_VERSION,
                "state": "INVALID_CANDIDATE",
                "risk_multiplier": 1.0,
                "paper_only": True,
                "live_execution": False,
            }
        if not peers:
            return {
                "success": True,
                "version": CORRELATION_VERSION,
                "state": "NO_OPEN_PEERS",
                "symbol": normalized_symbol,
                "timeframe": tf,
                "comparisons": [],
                "max_same_direction_correlation": None,
                "risk_multiplier": 1.0,
                "hard_blocker": None,
                "paper_only": True,
                "live_execution": False,
            }

        candidate = self._series(normalized_symbol, tf)
        if not candidate.get("success"):
            return {
                "success": True,
                "version": CORRELATION_VERSION,
                "state": "UNKNOWN_DATA_INSUFFICIENT",
                "symbol": normalized_symbol,
                "timeframe": tf,
                "source": candidate.get("source"),
                "comparisons": [],
                "max_same_direction_correlation": None,
                "risk_multiplier": 1.0,
                "hard_blocker": None,
                "data_fabricated": False,
                "paper_only": True,
                "live_execution": False,
            }

        peer_series: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(4, len(peers))) as pool:
            futures = {
                pool.submit(self._series, str(peer.get("symbol") or "").upper(), tf): peer
                for peer in peers
            }
            for future in as_completed(futures):
                peer = futures[future]
                try:
                    peer_series[str(peer.get("symbol") or "").upper()] = future.result()
                except Exception:
                    continue

        comparisons = []
        max_same: float | None = None
        for peer in peers:
            peer_symbol = str(peer.get("symbol") or "").upper()
            series = peer_series.get(peer_symbol)
            if not series or not series.get("success"):
                comparisons.append({
                    "symbol": peer_symbol,
                    "side": str(peer.get("side") or "").upper(),
                    "correlation": None,
                    "observations": 0,
                    "state": "UNKNOWN",
                })
                continue
            correlation, observations = self._pair(candidate, series)
            same_direction = str(peer.get("side") or "").upper() == normalized_side
            if correlation is not None and same_direction:
                max_same = correlation if max_same is None else max(max_same, correlation)
            comparisons.append({
                "symbol": peer_symbol,
                "side": str(peer.get("side") or "").upper(),
                "correlation": round(correlation, 4) if correlation is not None else None,
                "observations": observations,
                "same_direction": same_direction,
                "state": "MEASURED" if correlation is not None else "INSUFFICIENT_ALIGNED_BARS",
                "source": series.get("source"),
            })

        multiplier = 1.0
        state = "DIVERSIFIED_OR_UNKNOWN"
        if max_same is not None:
            if max_same >= 0.85:
                multiplier = 0.35
                state = "VERY_HIGH_SAME_DIRECTION_CORRELATION"
            elif max_same >= 0.70:
                multiplier = 0.55
                state = "HIGH_SAME_DIRECTION_CORRELATION"
            elif max_same >= 0.55:
                multiplier = 0.75
                state = "MODERATE_SAME_DIRECTION_CORRELATION"
            else:
                state = "LOW_SAME_DIRECTION_CORRELATION"

        return {
            "success": True,
            "version": CORRELATION_VERSION,
            "generated_at": _now(),
            "state": state,
            "symbol": normalized_symbol,
            "side": normalized_side,
            "timeframe": tf,
            "comparisons": comparisons,
            "max_same_direction_correlation": round(max_same, 4) if max_same is not None else None,
            "risk_multiplier": multiplier,
            "hard_blocker": None,
            "minimum_observations": MIN_OBSERVATIONS,
            "completed_bars_only": True,
            "forming_bar_excluded": True,
            "risk_can_only_be_reduced": True,
            "data_fabricated": False,
            "paper_desk_remains_final_risk_authority": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def snapshot(self) -> dict[str, Any]:
        try:
            from workstation.paper_trading_desk import paper_desk
            positions = list(paper_desk.snapshot().get("positions") or [])
        except Exception:
            positions = []
        return {
            "success": True,
            "version": "13.0",
            "service": CORRELATION_VERSION,
            "open_positions": len(positions),
            "minimum_observations": MIN_OBSERVATIONS,
            "max_open_comparisons": MAX_OPEN_COMPARISONS,
            "completed_bars_only": True,
            "unknown_when_data_missing": True,
            "risk_can_only_be_reduced": True,
            "paper_desk_final_authority": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


DYNAMIC_CORRELATION_RISK_V13 = DynamicCorrelationRiskV13()

__all__ = ["DYNAMIC_CORRELATION_RISK_V13", "DynamicCorrelationRiskV13", "CORRELATION_VERSION"]
