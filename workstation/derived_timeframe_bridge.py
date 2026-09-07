from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any, Iterable


_LOCK = RLock()
_INSTALLED = False
_ORIGINAL_CANDLES_PAYLOAD = None
_ORIGINAL_NORMALIZE_TIMEFRAME = None

_DERIVED_TIMEFRAME = "10m"
_SOURCE_TIMEFRAME = "5m"
_INTERVAL_SECONDS = 600
_SOURCE_INTERVAL_SECONDS = 300
_COMMODITY_SYMBOLS = {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}


def _timestamp(row: dict[str, Any]) -> int | None:
    value = row.get("time", row.get("timestamp"))
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _phase_seconds(symbol: str, quant_module: Any) -> int:
    """Return the 10-minute bucket phase for the resolved market session.

    Indian cash equities/indices open at :15, so their canonical 10-minute bars
    are offset by five minutes from UTC 10-minute boundaries. MCX instruments
    and 24x7/global feeds retain the normal zero phase. This avoids pairing
    09:15/09:20 with an unrelated 09:10 bucket.
    """

    try:
        canonical = quant_module.normalize_symbol(symbol)
    except Exception:
        canonical = str(symbol or "").strip().upper()
    if canonical in _COMMODITY_SYMBOLS:
        return 0
    try:
        metadata = quant_module.symbol_metadata(canonical)
    except Exception:
        metadata = {}
    if str(metadata.get("market") or "").upper() == "INDIA":
        return 300
    return 0


def aggregate_completed_10m(
    candles: Iterable[dict[str, Any]],
    *,
    phase_seconds: int = 0,
) -> list[dict[str, Any]]:
    """Aggregate only two contiguous completed 5m bars into one 10m bar.

    Missing or still-forming source bars are never synthesized. A 10m bucket is
    emitted only when both expected 5m opens are present exactly five minutes
    apart. The resulting candle therefore has explicit provenance back to the
    lower-timeframe provider data.
    """

    phase = int(phase_seconds) % _INTERVAL_SECONDS
    grouped: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    for raw in candles:
        if not isinstance(raw, dict):
            continue
        ts = _timestamp(raw)
        if ts is None:
            continue
        bucket = ts - ((ts - phase) % _INTERVAL_SECONDS)
        grouped[bucket][ts] = dict(raw)

    result: list[dict[str, Any]] = []
    for bucket in sorted(grouped):
        expected = (bucket, bucket + _SOURCE_INTERVAL_SECONDS)
        rows = grouped[bucket]
        if any(ts not in rows for ts in expected):
            continue
        first, second = rows[expected[0]], rows[expected[1]]
        try:
            candle = {
                "time": bucket,
                "timestamp": bucket,
                "open": float(first["open"]),
                "high": max(float(first["high"]), float(second["high"])),
                "low": min(float(first["low"]), float(second["low"])),
                "close": float(second["close"]),
                "volume": float(first.get("volume") or 0.0) + float(second.get("volume") or 0.0),
                "close_time": bucket + _INTERVAL_SECONDS,
                "derived": True,
                "derived_from": _SOURCE_TIMEFRAME,
                "source_bar_times": [expected[0], expected[1]],
            }
        except (KeyError, TypeError, ValueError):
            continue
        result.append(candle)
    return result


def install_derived_timeframe_bridge() -> dict[str, Any]:
    """Install the V11 10m completed-bar adapter into Quant runtime.

    The adapter is deliberately narrow: it extends only the read/research candle
    path and never touches broker execution. Calls for all existing timeframes
    continue through the original Quant Terminal implementation unchanged.
    """

    global _INSTALLED, _ORIGINAL_CANDLES_PAYLOAD, _ORIGINAL_NORMALIZE_TIMEFRAME
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation import quant_terminal_v2 as quant

        _ORIGINAL_CANDLES_PAYLOAD = quant.candles_payload
        _ORIGINAL_NORMALIZE_TIMEFRAME = quant.normalize_timeframe
        quant.SUPPORTED_TIMEFRAMES.add(_DERIVED_TIMEFRAME)
        if hasattr(quant, "_TIMEFRAME_SECONDS"):
            quant._TIMEFRAME_SECONDS[_DERIVED_TIMEFRAME] = _INTERVAL_SECONDS

        original_normalize = _ORIGINAL_NORMALIZE_TIMEFRAME
        original_payload = _ORIGINAL_CANDLES_PAYLOAD

        def normalize_timeframe_v11(value: str) -> str:
            token = str(value or "").strip().lower().replace(" ", "")
            if token in {"10", "10m", "10min", "10mins", "10minute", "10minutes"}:
                return _DERIVED_TIMEFRAME
            return original_normalize(value)

        def candles_payload_v11(
            symbol: str,
            timeframe: str = "5m",
            bars: int = 500,
        ) -> dict[str, Any]:
            resolved = normalize_timeframe_v11(timeframe)
            if resolved != _DERIVED_TIMEFRAME:
                return original_payload(symbol, timeframe, bars)

            requested_bars = max(20, min(int(bars), 3750))
            source_bars = min(7500, max(40, requested_bars * 2 + 8))
            base = original_payload(symbol, _SOURCE_TIMEFRAME, source_bars)
            raw = [dict(row) for row in list(base.get("candles") or []) if isinstance(row, dict)]
            completed = quant.completed_candles(raw, _SOURCE_TIMEFRAME)
            phase = _phase_seconds(symbol, quant)
            derived = aggregate_completed_10m(completed, phase_seconds=phase)
            bounded = derived[-requested_bars:]

            payload = dict(base)
            payload.update({
                "success": bool(base.get("success") and bounded),
                "timeframe": _DERIVED_TIMEFRAME,
                "bars": len(bounded),
                "candles": bounded,
                "derived": True,
                "derived_from_timeframe": _SOURCE_TIMEFRAME,
                "aggregation_contract": "TWO_CONTIGUOUS_COMPLETED_5M_BARS_ONLY",
                "aggregation_phase_seconds": phase,
                "source_bars_requested": source_bars,
                "source_completed_bars": len(completed),
                "forming_bar_excluded": len(completed) < len(raw),
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
            if bounded:
                payload["message"] = (
                    "10m candles derived from two contiguous completed 5m provider bars; "
                    "no missing or forming bars are synthesized."
                )
            elif base.get("success"):
                payload["message"] = "Insufficient contiguous completed 5m bars to derive 10m candles."
            return payload

        quant.normalize_timeframe = normalize_timeframe_v11
        quant.candles_payload = candles_payload_v11
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "11.0",
            "installed": _INSTALLED,
            "timeframe": _DERIVED_TIMEFRAME,
            "source_timeframe": _SOURCE_TIMEFRAME,
            "completed_bars_only": True,
            "synthetic_missing_bars": False,
            "forming_bars_used": False,
            "provider_data_required": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = [
    "aggregate_completed_10m",
    "install_derived_timeframe_bridge",
    "status",
]
