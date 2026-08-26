from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from workstation.advanced_pattern_engine import analyze_chart_patterns
from workstation.indicator_registry import INDICATOR_REGISTRY, IndicatorRegistry, normalize_ohlcv


@dataclass(frozen=True)
class SwingPoint:
    index: int
    time: Any
    price: float
    kind: str
    strength: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "time": self.time,
            "price": self.price,
            "kind": self.kind,
            "strength": self.strength,
        }


def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    previous = frame.close.shift(1)
    true_range = pd.concat(
        (frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()),
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def detect_swings(frame: pd.DataFrame, *, window: int = 2) -> tuple[list[SwingPoint], list[SwingPoint]]:
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    window = max(1, int(window))
    for index in range(window, len(frame) - window):
        high = float(frame.high.iloc[index])
        low = float(frame.low.iloc[index])
        surrounding_highs = frame.high.iloc[index - window : index + window + 1]
        surrounding_lows = frame.low.iloc[index - window : index + window + 1]
        if high == float(surrounding_highs.max()) and int((surrounding_highs == high).sum()) == 1:
            highs.append(SwingPoint(index, frame.time.iloc[index], high, "SWING_HIGH", window))
        if low == float(surrounding_lows.min()) and int((surrounding_lows == low).sum()) == 1:
            lows.append(SwingPoint(index, frame.time.iloc[index], low, "SWING_LOW", window))
    return highs, lows


def classify_structure(frame: pd.DataFrame, highs: list[SwingPoint], lows: list[SwingPoint], atr: float) -> dict[str, Any]:
    high_sequence = "UNKNOWN"
    low_sequence = "UNKNOWN"
    if len(highs) >= 2:
        high_sequence = "HH" if highs[-1].price > highs[-2].price else "LH" if highs[-1].price < highs[-2].price else "EH"
    if len(lows) >= 2:
        low_sequence = "HL" if lows[-1].price > lows[-2].price else "LL" if lows[-1].price < lows[-2].price else "EL"
    if high_sequence == "HH" and low_sequence == "HL":
        trend = "BULLISH"
    elif high_sequence == "LH" and low_sequence == "LL":
        trend = "BEARISH"
    else:
        trend = "RANGE_OR_TRANSITION"

    close = float(frame.close.iloc[-1])
    prior_close = float(frame.close.iloc[-2])
    previous_high = highs[-1].price if highs else float(frame.high.iloc[:-1].tail(20).max())
    previous_low = lows[-1].price if lows else float(frame.low.iloc[:-1].tail(20).min())
    bos = None
    choch = None
    if close > previous_high and prior_close <= previous_high:
        bos = "BULLISH_BOS"
        if trend == "BEARISH":
            choch = "BULLISH_CHOCH"
    elif close < previous_low and prior_close >= previous_low:
        bos = "BEARISH_BOS"
        if trend == "BULLISH":
            choch = "BEARISH_CHOCH"

    recent = frame.tail(20)
    range_width = float(recent.high.max() - recent.low.min())
    normalized_width = range_width / max(atr, 1e-12)
    state = "RANGE" if normalized_width <= 4.0 else "TREND_OR_EXPANSION"
    return {
        "trend": trend,
        "high_sequence": high_sequence,
        "low_sequence": low_sequence,
        "bos": bos,
        "choch": choch,
        "internal_structure": state,
        "external_high": previous_high,
        "external_low": previous_low,
        "range_width_atr": round(normalized_width, 4),
    }


def _zone_clusters(points: list[SwingPoint], frame: pd.DataFrame, atr: float, kind: str) -> list[dict[str, Any]]:
    tolerance = max(atr * 0.35, float(frame.close.iloc[-1]) * 0.001)
    clusters: list[list[SwingPoint]] = []
    for point in sorted(points, key=lambda item: item.price):
        target = next(
            (cluster for cluster in clusters if abs(np.mean([item.price for item in cluster]) - point.price) <= tolerance),
            None,
        )
        if target is None:
            clusters.append([point])
        else:
            target.append(point)
    volume_median = float(frame.volume.replace(0, np.nan).median()) if frame.volume.gt(0).any() else 0.0
    zones: list[dict[str, Any]] = []
    for cluster in clusters:
        prices = [item.price for item in cluster]
        center = float(np.mean(prices))
        last_index = max(item.index for item in cluster)
        recency = max(0.0, 1.0 - (len(frame) - 1 - last_index) / max(len(frame), 1))
        reaction = 0.0
        rejection = 0.0
        relative_volume = 0.0
        for point in cluster:
            future = frame.iloc[point.index + 1 : point.index + 6]
            if not future.empty:
                if kind == "RESISTANCE":
                    reaction = max(reaction, float((point.price - future.low.min()) / max(atr, 1e-12)))
                else:
                    reaction = max(reaction, float((future.high.max() - point.price) / max(atr, 1e-12)))
            candle = frame.iloc[point.index]
            candle_range = max(float(candle.high - candle.low), 1e-12)
            upper_wick = float(candle.high - max(candle.open, candle.close)) / candle_range
            lower_wick = float(min(candle.open, candle.close) - candle.low) / candle_range
            rejection = max(rejection, upper_wick if kind == "RESISTANCE" else lower_wick)
            if volume_median > 0:
                relative_volume = max(relative_volume, float(candle.volume / volume_median))
        touches = len(cluster)
        score = min(
            100.0,
            20.0
            + min(touches, 5) * 9.0
            + recency * 15.0
            + min(reaction, 3.0) * 7.0
            + rejection * 10.0
            + min(relative_volume, 2.0) * 4.0,
        )
        zones.append(
            {
                "kind": kind,
                "lower": center - tolerance,
                "upper": center + tolerance,
                "center": center,
                "touches": touches,
                "last_reaction_index": last_index,
                "reaction_atr": round(reaction, 4),
                "rejection_quality": round(rejection, 4),
                "relative_volume": round(relative_volume, 4) if relative_volume else None,
                "strength_score": round(score, 2),
                "invalidation": center + tolerance if kind == "RESISTANCE" else center - tolerance,
                "evidence": ["SWING_CLUSTER", "RECENCY", "REACTION", "WICK_REJECTION"],
            }
        )
    return sorted(zones, key=lambda item: (item["strength_score"], item["last_reaction_index"]), reverse=True)


def detect_supply_demand(frame: pd.DataFrame, atr: float) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for index in range(2, len(frame) - 1):
        before, base, after = frame.iloc[index - 1], frame.iloc[index], frame.iloc[index + 1]
        before_move = float(before.close - before.open)
        after_move = float(after.close - after.open)
        base_range = float(base.high - base.low)
        if base_range > max(atr * 0.8, 1e-12):
            continue
        before_direction = "RALLY" if before_move > atr * 0.5 else "DROP" if before_move < -atr * 0.5 else None
        after_direction = "RALLY" if after_move > atr * 0.7 else "DROP" if after_move < -atr * 0.7 else None
        if not before_direction or not after_direction:
            continue
        pattern = f"{before_direction}_BASE_{after_direction}"
        kind = "DEMAND" if after_direction == "RALLY" else "SUPPLY"
        later = frame.iloc[index + 2 :]
        tested = bool(((later.low <= base.high) & (later.high >= base.low)).any()) if not later.empty else False
        displacement = abs(after_move) / max(atr, 1e-12)
        score = min(95.0, 55.0 + min(displacement, 3.0) * 10.0 - (15.0 if tested else 0.0))
        zones.append(
            {
                "kind": kind,
                "pattern": pattern,
                "proximal": float(base.high if kind == "DEMAND" else base.low),
                "distal": float(base.low if kind == "DEMAND" else base.high),
                "fresh": not tested,
                "tested": tested,
                "mitigated": tested,
                "displacement_atr": round(displacement, 4),
                "quality_score": round(score, 2),
                "invalidation": float(base.low if kind == "DEMAND" else base.high),
                "index": index,
            }
        )
    return sorted(zones[-20:], key=lambda item: (item["fresh"], item["quality_score"], item["index"]), reverse=True)


def detect_liquidity(frame: pd.DataFrame, highs: list[SwingPoint], lows: list[SwingPoint], atr: float) -> dict[str, Any]:
    tolerance = max(atr * 0.2, float(frame.close.iloc[-1]) * 0.00075)

    def equal_groups(points: list[SwingPoint], label: str) -> list[dict[str, Any]]:
        groups = []
        for left, right in zip(points, points[1:]):
            if abs(left.price - right.price) <= tolerance:
                groups.append({"type": label, "level": (left.price + right.price) / 2, "indices": [left.index, right.index]})
        return groups[-8:]

    equal_highs = equal_groups(highs, "EQUAL_HIGHS")
    equal_lows = equal_groups(lows, "EQUAL_LOWS")
    sweeps: list[dict[str, Any]] = []
    for pool in equal_highs:
        level = float(pool["level"])
        for index in range(pool["indices"][-1] + 1, len(frame)):
            candle = frame.iloc[index]
            if candle.high > level + tolerance and candle.close < level:
                sweeps.append({"type": "BUY_SIDE_SWEEP", "level": level, "index": index, "rejected_close": float(candle.close)})
                break
    for pool in equal_lows:
        level = float(pool["level"])
        for index in range(pool["indices"][-1] + 1, len(frame)):
            candle = frame.iloc[index]
            if candle.low < level - tolerance and candle.close > level:
                sweeps.append({"type": "SELL_SIDE_SWEEP", "level": level, "index": index, "rejected_close": float(candle.close)})

    gaps: list[dict[str, Any]] = []
    for index in range(2, len(frame)):
        first, third = frame.iloc[index - 2], frame.iloc[index]
        if third.low > first.high:
            gaps.append({"type": "BULLISH_FVG", "lower": float(first.high), "upper": float(third.low), "index": index})
        elif third.high < first.low:
            gaps.append({"type": "BEARISH_FVG", "lower": float(third.high), "upper": float(first.low), "index": index})
    close = float(frame.close.iloc[-1])
    external_high, external_low = float(frame.high.tail(50).max()), float(frame.low.tail(50).min())
    equilibrium = (external_high + external_low) / 2
    return {
        "equal_highs": equal_highs,
        "equal_lows": equal_lows,
        "liquidity_pools": [*equal_highs, *equal_lows],
        "sweeps": sweeps[-10:],
        "fair_value_gaps": gaps[-20:],
        "dealing_range": {"high": external_high, "low": external_low, "equilibrium": equilibrium},
        "premium_discount": "PREMIUM" if close > equilibrium else "DISCOUNT" if close < equilibrium else "EQUILIBRIUM",
        "identity_claim": "NONE_PRICE_ACTION_HEURISTICS_ONLY",
    }


def candle_and_volatility_context(frame: pd.DataFrame, atr: float) -> dict[str, Any]:
    candle = frame.iloc[-1]
    span = max(float(candle.high - candle.low), 1e-12)
    body = abs(float(candle.close - candle.open))
    upper = float(candle.high - max(candle.open, candle.close))
    lower = float(min(candle.open, candle.close) - candle.low)
    ranges = frame.high - frame.low
    recent = float(ranges.tail(5).mean())
    baseline = float(ranges.iloc[-25:-5].mean()) if len(frame) >= 25 else float(ranges.mean())
    if baseline <= 0:
        volatility_state = "UNKNOWN"
    elif recent >= baseline * 1.35:
        volatility_state = "EXPANSION"
    elif recent <= baseline * 0.70:
        volatility_state = "COMPRESSION"
    else:
        volatility_state = "NORMAL"
    displacement = body / max(atr, 1e-12)
    return {
        "candle_anatomy": {
            "body_percent": round(body / span * 100, 2),
            "upper_wick_percent": round(upper / span * 100, 2),
            "lower_wick_percent": round(lower / span * 100, 2),
            "close_location": round(float((candle.close - candle.low) / span), 4),
            "direction": "BULLISH" if candle.close > candle.open else "BEARISH" if candle.close < candle.open else "DOJI",
        },
        "volatility_state": volatility_state,
        "displacement_atr": round(displacement, 4),
        "displacement": displacement >= 1.2,
    }


def period_levels(frame: pd.DataFrame, *, opening_range_bars: int = 3) -> dict[str, Any]:
    values = frame.copy()
    parsed = pd.to_datetime(values.time, unit="s", utc=True, errors="coerce") if pd.api.types.is_numeric_dtype(values.time) else pd.to_datetime(values.time, utc=True, errors="coerce")
    values["datetime"] = parsed
    valid = values.dropna(subset=["datetime"])
    result: dict[str, Any] = {"previous_day": None, "previous_week": None, "session": None, "opening_range": None}
    if valid.empty:
        return result
    values["date"] = values.datetime.dt.date
    values["week"] = values.datetime.dt.strftime("%G-W%V")
    dates = list(dict.fromkeys(values.date.tolist()))
    if len(dates) >= 2:
        previous = values[values.date == dates[-2]]
        result["previous_day"] = {"high": float(previous.high.max()), "low": float(previous.low.min()), "close": float(previous.close.iloc[-1])}
    weeks = list(dict.fromkeys(values.week.tolist()))
    if len(weeks) >= 2:
        previous = values[values.week == weeks[-2]]
        result["previous_week"] = {"high": float(previous.high.max()), "low": float(previous.low.min()), "close": float(previous.close.iloc[-1])}
    session = values[values.date == dates[-1]]
    result["session"] = {"high": float(session.high.max()), "low": float(session.low.min()), "open": float(session.open.iloc[0])}
    opening = session.head(max(1, int(opening_range_bars)))
    result["opening_range"] = {"high": float(opening.high.max()), "low": float(opening.low.min()), "bars": len(opening)}
    return result


class UnifiedFeatureEngine:
    def __init__(self, indicator_registry: IndicatorRegistry | None = None) -> None:
        self.indicators = indicator_registry or INDICATOR_REGISTRY

    def analyze(
        self,
        candles: Iterable[Mapping[str, Any]],
        *,
        symbol: str,
        timeframe: str,
        provider: str | None = None,
        provider_symbol: str | None = None,
        data_quality: str | None = None,
        verified: bool = True,
        stale: bool = False,
        include_indicator_series: bool = False,
    ) -> dict[str, Any]:
        rows = list(candles)
        frame = normalize_ohlcv(rows)
        if len(frame) < 55:
            return {
                "success": False,
                "symbol": str(symbol).upper(),
                "timeframe": timeframe,
                "bars": len(frame),
                "message": "At least 55 valid completed OHLCV bars are required.",
                "paper_only": True,
                "live_execution": False,
            }
        atr_series = _atr(frame)
        valid_atr = atr_series.dropna()
        if valid_atr.empty or float(valid_atr.iloc[-1]) <= 0:
            return {
                "success": False,
                "symbol": str(symbol).upper(),
                "timeframe": timeframe,
                "bars": len(frame),
                "message": "ATR could not be established from verified bars.",
                "paper_only": True,
                "live_execution": False,
            }
        atr = float(valid_atr.iloc[-1])
        highs, lows = detect_swings(frame)
        structure = classify_structure(frame, highs, lows, atr)
        support = _zone_clusters(lows, frame, atr, "SUPPORT")
        resistance = _zone_clusters(highs, frame, atr, "RESISTANCE")
        supply_demand = detect_supply_demand(frame, atr)
        liquidity = detect_liquidity(frame, highs, lows, atr)
        context = candle_and_volatility_context(frame, atr)
        indicator_results = self.indicators.calculate_many(
            (
                ("EMA", {"period": 20}),
                ("EMA", {"period": 50}),
                "RSI",
                "ATR",
                "VWAP",
                "Anchored VWAP",
                "Relative Volume",
                "Bollinger Bands",
                "Donchian",
            ),
            rows,
        )
        # Identical indicator names with different parameters need explicit
        # stable keys in the feature snapshot.
        ema20 = self.indicators.calculate("EMA", rows, parameters={"period": 20})
        ema50 = self.indicators.calculate("EMA", rows, parameters={"period": 50})
        indicator_results["results"]["ema_20"] = ema20
        indicator_results["results"]["ema_50"] = ema50
        if not include_indicator_series:
            for result in indicator_results["results"].values():
                result["series"] = {}
        pattern = analyze_chart_patterns([dict(row) for row in frame.to_dict("records")])
        generated_at = datetime.now(timezone.utc).isoformat()
        return {
            "success": True,
            "feature_version": "UNIFIED_FEATURE_ENGINE_V1",
            "symbol": str(symbol).upper(),
            "timeframe": timeframe,
            "bars": len(frame),
            "generated_at": generated_at,
            "data": {
                "provider": provider,
                "provider_symbol": provider_symbol,
                "quality": data_quality,
                "verified": bool(verified),
                "stale": bool(stale),
                "last_time": frame.time.iloc[-1],
            },
            "price": float(frame.close.iloc[-1]),
            "atr": atr,
            "structure": structure,
            "swings": {"highs": [item.to_dict() for item in highs[-20:]], "lows": [item.to_dict() for item in lows[-20:]]},
            "support_resistance": {"support": support[:8], "resistance": resistance[:8]},
            "supply_demand": supply_demand[:12],
            "liquidity": liquidity,
            "candle_volatility": context,
            "period_levels": period_levels(frame),
            "patterns": pattern,
            "indicators": indicator_results,
            "explainability": {
                "deterministic": True,
                "lookahead_safe": True,
                "institution_identity_claimed": False,
                "notes": [
                    "All features are derived from supplied completed OHLCV bars.",
                    "Liquidity, order-block and institutional concepts are price-action heuristics only.",
                ],
            },
            "paper_only": True,
            "live_execution": False,
        }


UNIFIED_FEATURE_ENGINE = UnifiedFeatureEngine()
