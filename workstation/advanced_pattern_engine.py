from __future__ import annotations

import math
from typing import Any


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def analyze_chart_patterns(
    candles: list[dict[str, Any]],
    *,
    breakout_lookback: int = 20,
) -> dict[str, Any]:
    """Return bounded, explainable price/volume pattern evidence.

    The latest candle is never allowed to define its own breakout level. This
    prevents the look-ahead bug that makes every timeframe appear to signal.
    """

    if len(candles) < max(55, breakout_lookback + 3):
        return {
            "success": False,
            "state": "INSUFFICIENT_DATA",
            "direction": "NEUTRAL",
            "score": 0.0,
            "patterns": [],
            "message": "At least 55 complete candles are required for pattern analysis.",
        }

    rows = candles[-max(80, breakout_lookback + 35) :]
    last = rows[-1]
    previous = rows[-2]
    prior = rows[-breakout_lookback - 1 : -1]
    close = _finite(last.get("close"))
    prior_high = max(_finite(row.get("high")) for row in prior)
    prior_low = min(_finite(row.get("low")) for row in prior)
    ranges = [max(_finite(row.get("high")) - _finite(row.get("low")), 0.0) for row in rows[-15:]]
    atr_proxy = sum(ranges) / max(len(ranges), 1)
    volumes = [_finite(row.get("volume")) for row in prior]
    volume_mean = sum(volumes) / max(len(volumes), 1)
    volume_ratio = _finite(last.get("volume")) / volume_mean if volume_mean > 0 else 0.0
    proximity_band = max(atr_proxy * 0.5, close * 0.0075)

    bullish_breakout = close > prior_high
    bearish_breakdown = close < prior_low
    near_high = 0 <= prior_high - close <= proximity_band
    near_low = 0 <= close - prior_low <= proximity_band
    volume_confirmed = volume_ratio >= 1.20

    patterns: list[dict[str, Any]] = []
    if _finite(last.get("high")) <= _finite(previous.get("high")) and _finite(last.get("low")) >= _finite(previous.get("low")):
        patterns.append({"name": "INSIDE_BAR", "direction": "NEUTRAL", "strength": 1})
    if (
        _finite(previous.get("close")) < _finite(previous.get("open"))
        and close > _finite(last.get("open"))
        and _finite(last.get("open")) <= _finite(previous.get("close"))
        and close >= _finite(previous.get("open"))
    ):
        patterns.append({"name": "BULLISH_ENGULFING", "direction": "BULLISH", "strength": 2})
    if (
        _finite(previous.get("close")) > _finite(previous.get("open"))
        and close < _finite(last.get("open"))
        and _finite(last.get("open")) >= _finite(previous.get("close"))
        and close <= _finite(previous.get("open"))
    ):
        patterns.append({"name": "BEARISH_ENGULFING", "direction": "BEARISH", "strength": 2})

    closes = [_finite(row.get("close")) for row in rows]
    recent_avg = sum(closes[-10:]) / 10.0
    older_avg = sum(closes[-30:-10]) / 20.0
    structure = "BULLISH" if recent_avg > older_avg else "BEARISH" if recent_avg < older_avg else "NEUTRAL"

    if bullish_breakout:
        state = "CONFIRMED_BREAKOUT" if volume_confirmed else "UNCONFIRMED_BREAKOUT"
        direction = "BULLISH"
        score = 78.0 if volume_confirmed else 62.0
    elif bearish_breakdown:
        state = "CONFIRMED_BREAKDOWN" if volume_confirmed else "UNCONFIRMED_BREAKDOWN"
        direction = "BEARISH"
        score = 78.0 if volume_confirmed else 62.0
    elif near_high:
        state = "BREAKOUT_WATCH"
        direction = "BULLISH"
        score = 58.0 + min(volume_ratio, 1.5) * 6.0
    elif near_low:
        state = "BREAKDOWN_WATCH"
        direction = "BEARISH"
        score = 58.0 + min(volume_ratio, 1.5) * 6.0
    else:
        state = "NO_EDGE"
        direction = structure
        score = 35.0

    if direction == structure and direction in {"BULLISH", "BEARISH"}:
        score += 5.0
    if any(item["direction"] == direction for item in patterns):
        score += 4.0
    score = round(min(score, 95.0), 2)

    distance_to_breakout = ((prior_high - close) / close * 100.0) if close else None
    distance_to_breakdown = ((close - prior_low) / close * 100.0) if close else None
    return {
        "success": True,
        "state": state,
        "direction": direction,
        "score": score,
        "structure": structure,
        "breakout_level": prior_high,
        "breakdown_level": prior_low,
        "distance_to_breakout_percent": distance_to_breakout,
        "distance_to_breakdown_percent": distance_to_breakdown,
        "volume_ratio": volume_ratio if volume_mean > 0 else None,
        "volume_confirmed": volume_confirmed,
        "atr_proxy": atr_proxy,
        "patterns": patterns[-6:],
        "lookback": breakout_lookback,
        "lookahead_safe": True,
        "message": (
            f"{state.replace('_', ' ')}; structure {structure}; "
            f"volume {volume_ratio:.2f}x." if volume_mean > 0 else f"{state.replace('_', ' ')}; structure {structure}."
        ),
    }

