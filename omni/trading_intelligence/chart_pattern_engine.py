from __future__ import annotations

from statistics import fmean
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float:
    if len(candles) <= period:
        return 0.0
    values = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        high = _f(current.get("high"))
        low = _f(current.get("low"))
        previous_close = _f(previous.get("close"))
        values.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return fmean(values) if values else 0.0


def _swings(candles: list[dict[str, Any]], left: int = 2, right: int = 2):
    highs = []
    lows = []
    for index in range(left, len(candles) - right):
        high = _f(candles[index].get("high"))
        low = _f(candles[index].get("low"))
        local_highs = [_f(candles[j].get("high")) for j in range(index - left, index + right + 1)]
        local_lows = [_f(candles[j].get("low")) for j in range(index - left, index + right + 1)]
        if high >= max(local_highs):
            highs.append((index, high))
        if low <= min(local_lows):
            lows.append((index, low))
    return highs, lows


def detect_chart_patterns(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect a conservative set of higher-order chart patterns.

    These are heuristic research labels, not guarantees. A downstream strategy
    still needs regime, risk and confirmation gates before paper execution.
    """

    if len(candles) < 40:
        return []
    sample = candles[-160:]
    highs, lows = _swings(sample)
    atr = max(_atr(sample), 1e-9)
    close = _f(sample[-1].get("close"))
    tolerance = max(atr * 0.65, close * 0.0035)
    result: list[dict[str, Any]] = []

    if len(highs) >= 2:
        (i1, h1), (i2, h2) = highs[-2], highs[-1]
        if i2 - i1 >= 4 and abs(h2 - h1) <= tolerance:
            neckline_candidates = [_f(row.get("low")) for row in sample[i1:i2 + 1]]
            neckline = min(neckline_candidates) if neckline_candidates else None
            result.append(
                {
                    "pattern": "DOUBLE_TOP",
                    "bias": "BEARISH",
                    "confidence": 0.62,
                    "level": (h1 + h2) / 2.0,
                    "neckline": neckline,
                }
            )

    if len(lows) >= 2:
        (i1, l1), (i2, l2) = lows[-2], lows[-1]
        if i2 - i1 >= 4 and abs(l2 - l1) <= tolerance:
            neckline_candidates = [_f(row.get("high")) for row in sample[i1:i2 + 1]]
            neckline = max(neckline_candidates) if neckline_candidates else None
            result.append(
                {
                    "pattern": "DOUBLE_BOTTOM",
                    "bias": "BULLISH",
                    "confidence": 0.62,
                    "level": (l1 + l2) / 2.0,
                    "neckline": neckline,
                }
            )

    if len(highs) >= 3:
        left, head, right = highs[-3], highs[-2], highs[-1]
        shoulders_close = abs(left[1] - right[1]) <= tolerance * 1.5
        head_above = head[1] >= max(left[1], right[1]) + tolerance * 0.6
        if shoulders_close and head_above:
            result.append(
                {
                    "pattern": "HEAD_AND_SHOULDERS",
                    "bias": "BEARISH",
                    "confidence": 0.66,
                    "left_shoulder": left[1],
                    "head": head[1],
                    "right_shoulder": right[1],
                }
            )

    if len(lows) >= 3:
        left, head, right = lows[-3], lows[-2], lows[-1]
        shoulders_close = abs(left[1] - right[1]) <= tolerance * 1.5
        head_below = head[1] <= min(left[1], right[1]) - tolerance * 0.6
        if shoulders_close and head_below:
            result.append(
                {
                    "pattern": "INVERSE_HEAD_AND_SHOULDERS",
                    "bias": "BULLISH",
                    "confidence": 0.66,
                    "left_shoulder": left[1],
                    "head": head[1],
                    "right_shoulder": right[1],
                }
            )

    if len(highs) >= 3 and len(lows) >= 3:
        recent_highs = [value for _, value in highs[-3:]]
        recent_lows = [value for _, value in lows[-3:]]
        high_slope = recent_highs[-1] - recent_highs[0]
        low_slope = recent_lows[-1] - recent_lows[0]
        if high_slope < -tolerance * 0.3 and low_slope > tolerance * 0.3:
            result.append(
                {
                    "pattern": "SYMMETRICAL_COMPRESSION",
                    "bias": "BREAKOUT_PENDING",
                    "confidence": 0.55,
                }
            )
        elif abs(high_slope) <= tolerance and low_slope > tolerance * 0.4:
            result.append(
                {
                    "pattern": "ASCENDING_TRIANGLE",
                    "bias": "BULLISH",
                    "confidence": 0.58,
                }
            )
        elif abs(low_slope) <= tolerance and high_slope < -tolerance * 0.4:
            result.append(
                {
                    "pattern": "DESCENDING_TRIANGLE",
                    "bias": "BEARISH",
                    "confidence": 0.58,
                }
            )

    recent = sample[-20:]
    recent_high = max(_f(row.get("high")) for row in recent[:-1])
    recent_low = min(_f(row.get("low")) for row in recent[:-1])
    if close > recent_high:
        result.append(
            {
                "pattern": "RANGE_BREAKOUT",
                "bias": "BULLISH",
                "confidence": 0.60,
                "level": recent_high,
            }
        )
    elif close < recent_low:
        result.append(
            {
                "pattern": "RANGE_BREAKDOWN",
                "bias": "BEARISH",
                "confidence": 0.60,
                "level": recent_low,
            }
        )

    return result[-10:]
