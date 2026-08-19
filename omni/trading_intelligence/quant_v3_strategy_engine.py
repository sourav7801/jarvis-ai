from __future__ import annotations

"""Fast, deterministic strategy ensemble for JARVIS Quant V3.

The engine is deliberately broker-write-free.  It evaluates a broad library of
price/volume/structure strategies on already-normalized candles, classifies the
current regime, and produces a research/paper consensus with timing telemetry.

A high win rate is never treated as a guarantee or as the sole optimization
objective.  Production-quality selection is expected to use the repository's
walk-forward/OOS/cost/Monte-Carlo validation stack before a strategy receives
material paper weight.
"""

from dataclasses import dataclass
from math import sqrt
from statistics import fmean, pstdev
from time import perf_counter_ns
from typing import Any, Iterable


SIGNAL_VALUE = {"LONG": 1.0, "SHORT": -1.0, "FLAT": 0.0}


@dataclass(frozen=True)
class StrategyVote:
    strategy_id: str
    family: str
    signal: str
    strength: float
    weight: float
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "family": self.family,
            "signal": self.signal,
            "strength": round(float(self.strength), 6),
            "weight": round(float(self.weight), 6),
            "evidence": list(self.evidence),
        }


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number else default
    except Exception:
        return default


def _rows(candles: Iterable[dict[str, Any]]) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for row in candles:
        try:
            item = {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or 0.0),
                "time": float(row.get("time", row.get("timestamp", 0)) or 0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        if item["high"] < item["low"]:
            continue
        output.append(item)
    return output


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    current = fmean(values[:period])
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return fmean(values[-period:])


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [b - a for a, b in zip(values[-period - 1 : -1], values[-period:])]
    gains = [max(value, 0.0) for value in changes]
    losses = [max(-value, 0.0) for value in changes]
    avg_gain = fmean(gains)
    avg_loss = fmean(losses)
    if avg_loss <= 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _atr(rows: list[dict[str, float]], period: int = 14) -> float | None:
    if len(rows) <= period:
        return None
    values: list[float] = []
    for previous, current in zip(rows[-period - 1 : -1], rows[-period:]):
        values.append(
            max(
                current["high"] - current["low"],
                abs(current["high"] - previous["close"]),
                abs(current["low"] - previous["close"]),
            )
        )
    return fmean(values) if values else None


def _vwap(rows: list[dict[str, float]], period: int = 50) -> float | None:
    sample = rows[-period:]
    denominator = sum(row["volume"] for row in sample)
    if denominator <= 0:
        return _sma([row["close"] for row in sample], min(20, len(sample)))
    numerator = sum(
        ((row["high"] + row["low"] + row["close"]) / 3.0) * row["volume"]
        for row in sample
    )
    return numerator / denominator


def _stochastic(rows: list[dict[str, float]], period: int = 14) -> float | None:
    if len(rows) < period:
        return None
    sample = rows[-period:]
    high = max(row["high"] for row in sample)
    low = min(row["low"] for row in sample)
    if high <= low:
        return 50.0
    return (rows[-1]["close"] - low) / (high - low) * 100.0


def _bollinger(values: list[float], period: int = 20, sigma: float = 2.0):
    if len(values) < period:
        return None, None, None
    sample = values[-period:]
    mid = fmean(sample)
    std = pstdev(sample)
    return mid - sigma * std, mid, mid + sigma * std


def _volume_ratio(rows: list[dict[str, float]], period: int = 20) -> float | None:
    if len(rows) < period + 1:
        return None
    baseline = fmean(row["volume"] for row in rows[-period - 1 : -1])
    if baseline <= 0:
        return None
    return rows[-1]["volume"] / baseline


def _realized_vol(values: list[float], period: int = 20) -> float | None:
    if len(values) <= period:
        return None
    returns = []
    for left, right in zip(values[-period - 1 : -1], values[-period:]):
        if left:
            returns.append(right / left - 1.0)
    return pstdev(returns) if len(returns) >= 2 else 0.0


def _macd(values: list[float]):
    fast = _ema(values, 12)
    slow = _ema(values, 26)
    if fast is None or slow is None:
        return None
    return fast - slow


def _structure(rows: list[dict[str, float]], lookback: int = 8) -> str:
    if len(rows) < lookback + 1:
        return "MIXED"
    sample = rows[-lookback:]
    split = max(2, lookback // 2)
    old = sample[:split]
    new = sample[split:]
    old_high, new_high = max(x["high"] for x in old), max(x["high"] for x in new)
    old_low, new_low = min(x["low"] for x in old), min(x["low"] for x in new)
    if new_high > old_high and new_low > old_low:
        return "BULLISH"
    if new_high < old_high and new_low < old_low:
        return "BEARISH"
    return "MIXED"


def _latest_fvg(rows: list[dict[str, float]]) -> dict[str, Any] | None:
    if len(rows) < 3:
        return None
    a, _, c = rows[-3], rows[-2], rows[-1]
    if c["low"] > a["high"]:
        return {"direction": "BULLISH", "lower": a["high"], "upper": c["low"]}
    if c["high"] < a["low"]:
        return {"direction": "BEARISH", "lower": c["high"], "upper": a["low"]}
    return None


def _liquidity_sweep(rows: list[dict[str, float]], lookback: int = 20) -> str | None:
    if len(rows) < lookback + 2:
        return None
    current = rows[-1]
    reference = rows[-lookback - 1 : -1]
    prior_high = max(row["high"] for row in reference)
    prior_low = min(row["low"] for row in reference)
    if current["high"] > prior_high and current["close"] < prior_high:
        return "BEARISH"
    if current["low"] < prior_low and current["close"] > prior_low:
        return "BULLISH"
    return None


def _feature_snapshot(rows: list[dict[str, float]]) -> dict[str, Any]:
    closes = [row["close"] for row in rows]
    ema9, ema21, ema50 = _ema(closes, 9), _ema(closes, 21), _ema(closes, 50)
    lower, basis, upper = _bollinger(closes)
    atr14 = _atr(rows)
    rv20 = _realized_vol(closes)
    previous_macd = _macd(closes[:-1]) if len(closes) > 27 else None
    current_macd = _macd(closes)
    sample20 = rows[-21:-1] if len(rows) >= 21 else rows[:-1]
    previous_high = max((row["high"] for row in sample20), default=None)
    previous_low = min((row["low"] for row in sample20), default=None)
    return {
        "close": closes[-1],
        "open": rows[-1]["open"],
        "high": rows[-1]["high"],
        "low": rows[-1]["low"],
        "ema9": ema9,
        "ema21": ema21,
        "ema50": ema50,
        "rsi14": _rsi(closes),
        "atr14": atr14,
        "atr_pct": (atr14 / closes[-1]) if atr14 and closes[-1] else None,
        "vwap": _vwap(rows),
        "stochastic14": _stochastic(rows),
        "bollinger_lower": lower,
        "bollinger_mid": basis,
        "bollinger_upper": upper,
        "macd": current_macd,
        "macd_previous": previous_macd,
        "volume_ratio": _volume_ratio(rows),
        "realized_vol20": rv20,
        "previous_20_high": previous_high,
        "previous_20_low": previous_low,
        "structure": _structure(rows),
        "fvg": _latest_fvg(rows),
        "liquidity_sweep": _liquidity_sweep(rows),
    }


def _regime(features: dict[str, Any]) -> str:
    close = _f(features.get("close"))
    ema9 = features.get("ema9")
    ema21 = features.get("ema21")
    ema50 = features.get("ema50")
    atr_pct = _f(features.get("atr_pct"))
    rv = _f(features.get("realized_vol20"))
    if None in (ema9, ema21, ema50):
        return "UNKNOWN"
    high_vol = atr_pct >= 0.008 or rv >= 0.008
    if close > ema9 > ema21 > ema50:
        return "TREND_UP_HIGH_VOL" if high_vol else "TREND_UP"
    if close < ema9 < ema21 < ema50:
        return "TREND_DOWN_HIGH_VOL" if high_vol else "TREND_DOWN"
    return "RANGE_HIGH_VOL" if high_vol else "RANGE"


def _vote(strategy_id: str, family: str, signal: str, strength: float, weight: float, *evidence: str):
    return StrategyVote(
        strategy_id=strategy_id,
        family=family,
        signal=signal,
        strength=max(0.0, min(1.0, float(strength))),
        weight=max(0.0, float(weight)),
        evidence=tuple(item for item in evidence if item),
    )


def _strategy_votes(features: dict[str, Any], regime: str) -> list[StrategyVote]:
    close = _f(features.get("close"))
    ema9, ema21, ema50 = features.get("ema9"), features.get("ema21"), features.get("ema50")
    rsi = features.get("rsi14")
    vwap = features.get("vwap")
    lower, upper = features.get("bollinger_lower"), features.get("bollinger_upper")
    stochastic = features.get("stochastic14")
    macd, macd_prev = features.get("macd"), features.get("macd_previous")
    vol_ratio = features.get("volume_ratio")
    atr_pct = _f(features.get("atr_pct"))
    high20, low20 = features.get("previous_20_high"), features.get("previous_20_low")
    structure = str(features.get("structure") or "MIXED")
    fvg = features.get("fvg")
    sweep = features.get("liquidity_sweep")

    votes: list[StrategyVote] = []
    trending = regime.startswith("TREND")
    ranging = regime.startswith("RANGE")
    high_vol = regime.endswith("HIGH_VOL")

    if None not in (ema9, ema21, ema50):
        signal = "LONG" if close > ema9 > ema21 > ema50 else "SHORT" if close < ema9 < ema21 < ema50 else "FLAT"
        votes.append(_vote("ema_stack_trend_v3", "trend", signal, 0.82 if signal != "FLAT" else 0.2, 1.45 if trending else 0.7, f"EMA stack {signal.lower()}"))

    if vwap is not None and ema9 is not None and ema21 is not None:
        signal = "LONG" if close > vwap and ema9 > ema21 else "SHORT" if close < vwap and ema9 < ema21 else "FLAT"
        votes.append(_vote("vwap_momentum_v3", "momentum", signal, 0.78 if signal != "FLAT" else 0.2, 1.3 if trending else 0.9, "price/VWAP + EMA alignment"))

    if rsi is not None and vwap is not None:
        signal = "LONG" if rsi <= 30 and close < vwap else "SHORT" if rsi >= 70 and close > vwap else "FLAT"
        votes.append(_vote("rsi_vwap_mean_reversion_v3", "mean_reversion", signal, min(1.0, abs(rsi - 50.0) / 35.0), 1.4 if ranging else 0.45, f"RSI {rsi:.1f}"))

    if lower is not None and upper is not None and rsi is not None:
        signal = "LONG" if close <= lower and rsi < 40 else "SHORT" if close >= upper and rsi > 60 else "FLAT"
        votes.append(_vote("bollinger_reversion_v3", "mean_reversion", signal, 0.75 if signal != "FLAT" else 0.15, 1.2 if ranging else 0.5, "Bollinger extreme"))

    if high20 is not None and low20 is not None:
        signal = "LONG" if close > high20 else "SHORT" if close < low20 else "FLAT"
        strength = min(1.0, 0.55 + max(0.0, (_f(vol_ratio, 1.0) - 1.0)) * 0.2) if signal != "FLAT" else 0.15
        votes.append(_vote("donchian_breakout_v3", "breakout", signal, strength, 1.45 if high_vol or trending else 0.8, "20-bar breakout"))

    if macd is not None and macd_prev is not None:
        signal = "LONG" if macd > 0 and macd > macd_prev else "SHORT" if macd < 0 and macd < macd_prev else "FLAT"
        votes.append(_vote("macd_impulse_v3", "momentum", signal, 0.68 if signal != "FLAT" else 0.15, 1.0 if trending else 0.65, "MACD impulse"))

    if stochastic is not None:
        signal = "LONG" if stochastic <= 15 else "SHORT" if stochastic >= 85 else "FLAT"
        votes.append(_vote("stochastic_extreme_v3", "mean_reversion", signal, 0.7 if signal != "FLAT" else 0.1, 0.9 if ranging else 0.35, f"stochastic {stochastic:.1f}"))

    if vol_ratio is not None and high20 is not None and low20 is not None:
        signal = "LONG" if vol_ratio >= 1.8 and close > high20 else "SHORT" if vol_ratio >= 1.8 and close < low20 else "FLAT"
        votes.append(_vote("relative_volume_breakout_v3", "volume_breakout", signal, min(1.0, vol_ratio / 3.0) if signal != "FLAT" else 0.1, 1.35 if high_vol else 1.0, f"volume ratio {vol_ratio:.2f}"))

    if None not in (ema21, ema50) and rsi is not None:
        signal = "LONG" if ema21 > ema50 and 42 <= rsi <= 60 and close >= ema21 else "SHORT" if ema21 < ema50 and 40 <= rsi <= 58 and close <= ema21 else "FLAT"
        votes.append(_vote("trend_pullback_v3", "pullback", signal, 0.7 if signal != "FLAT" else 0.12, 1.25 if trending else 0.5, "EMA21 pullback + RSI"))

    signal = "LONG" if structure == "BULLISH" else "SHORT" if structure == "BEARISH" else "FLAT"
    votes.append(_vote("market_structure_v3", "structure", signal, 0.68 if signal != "FLAT" else 0.15, 1.05, f"structure {structure.lower()}"))

    if fvg:
        signal = "LONG" if fvg["direction"] == "BULLISH" else "SHORT"
        votes.append(_vote("fair_value_gap_v3", "imbalance", signal, 0.58, 0.75 if trending else 0.55, f"{fvg['direction'].lower()} FVG"))
    else:
        votes.append(_vote("fair_value_gap_v3", "imbalance", "FLAT", 0.1, 0.6, "no fresh three-candle gap"))

    if sweep:
        signal = "LONG" if sweep == "BULLISH" else "SHORT"
        votes.append(_vote("liquidity_sweep_v3", "liquidity", signal, 0.66, 0.95 if ranging else 0.75, f"{sweep.lower()} liquidity sweep"))
    else:
        votes.append(_vote("liquidity_sweep_v3", "liquidity", "FLAT", 0.1, 0.75, "no confirmed sweep"))

    if atr_pct > 0:
        direction = "LONG" if close > _f(ema21, close) else "SHORT" if close < _f(ema21, close) else "FLAT"
        signal = direction if atr_pct >= 0.006 else "FLAT"
        votes.append(_vote("volatility_expansion_v3", "volatility", signal, min(1.0, atr_pct / 0.018) if signal != "FLAT" else 0.1, 1.3 if high_vol else 0.55, f"ATR% {atr_pct * 100:.2f}"))

    return votes


def _apply_derivatives_confirmation(votes: list[StrategyVote], option_context: dict[str, Any] | None) -> list[StrategyVote]:
    if not option_context:
        return votes
    score = _f(option_context.get("confirmation_score"))
    liquidity = _f(option_context.get("liquidity_score"))
    if liquidity < 20:
        signal = "FLAT"
        strength = 0.1
    elif score >= 0.25:
        signal, strength = "LONG", min(1.0, abs(score))
    elif score <= -0.25:
        signal, strength = "SHORT", min(1.0, abs(score))
    else:
        signal, strength = "FLAT", 0.2
    votes.append(
        _vote(
            "derivatives_confirmation_v3",
            "derivatives",
            signal,
            strength,
            1.25,
            f"derivatives score {score:.2f}",
            f"liquidity {liquidity:.1f}",
        )
    )
    return votes


def strategy_catalog() -> tuple[dict[str, Any], ...]:
    return (
        {"id": "ema_stack_trend_v3", "family": "trend"},
        {"id": "vwap_momentum_v3", "family": "momentum"},
        {"id": "rsi_vwap_mean_reversion_v3", "family": "mean_reversion"},
        {"id": "bollinger_reversion_v3", "family": "mean_reversion"},
        {"id": "donchian_breakout_v3", "family": "breakout"},
        {"id": "macd_impulse_v3", "family": "momentum"},
        {"id": "stochastic_extreme_v3", "family": "mean_reversion"},
        {"id": "relative_volume_breakout_v3", "family": "volume_breakout"},
        {"id": "trend_pullback_v3", "family": "pullback"},
        {"id": "market_structure_v3", "family": "structure"},
        {"id": "fair_value_gap_v3", "family": "imbalance"},
        {"id": "liquidity_sweep_v3", "family": "liquidity"},
        {"id": "volatility_expansion_v3", "family": "volatility"},
        {"id": "derivatives_confirmation_v3", "family": "derivatives"},
    )


def evaluate_strategies(
    candles: Iterable[dict[str, Any]],
    *,
    symbol: str = "UNKNOWN",
    timeframe: str = "5m",
    option_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = perf_counter_ns()
    rows = _rows(candles)
    if len(rows) < 55:
        return {
            "success": False,
            "symbol": symbol,
            "timeframe": timeframe,
            "message": "At least 55 valid candles are required for Quant V3.",
            "paper_only": True,
            "live_execution": False,
        }

    feature_start = perf_counter_ns()
    features = _feature_snapshot(rows)
    regime = _regime(features)
    feature_ns = perf_counter_ns() - feature_start

    strategy_start = perf_counter_ns()
    votes = _apply_derivatives_confirmation(_strategy_votes(features, regime), option_context)
    weighted = 0.0
    mass = 0.0
    for vote in votes:
        effective = vote.weight * max(0.05, vote.strength)
        weighted += SIGNAL_VALUE[vote.signal] * effective
        mass += effective
    score = weighted / mass if mass else 0.0
    threshold = 0.22
    consensus = "LONG" if score >= threshold else "SHORT" if score <= -threshold else "FLAT"
    confidence = min(0.95, abs(score)) if consensus != "FLAT" else max(0.0, 1.0 - abs(score) / threshold) * 0.35
    strategy_ns = perf_counter_ns() - strategy_start
    elapsed_ns = perf_counter_ns() - started

    active = [vote for vote in votes if vote.signal != "FLAT"]
    active.sort(key=lambda item: item.weight * item.strength, reverse=True)

    return {
        "success": True,
        "symbol": str(symbol),
        "timeframe": str(timeframe),
        "regime": regime,
        "consensus": consensus,
        "ensemble_score": round(score, 6),
        "confidence": round(confidence, 6),
        "strategy_count": len(votes),
        "active_strategy_count": len(active),
        "top_drivers": [vote.to_dict() for vote in active[:5]],
        "votes": [vote.to_dict() for vote in votes],
        "features": features,
        "latency": {
            "feature_ms": round(feature_ns / 1_000_000.0, 4),
            "strategy_ms": round(strategy_ns / 1_000_000.0, 4),
            "total_ms": round(elapsed_ns / 1_000_000.0, 4),
        },
        "decision_model": "regime_weighted_multi_strategy_ensemble",
        "win_rate_is_not_probability": True,
        "paper_only": True,
        "live_execution": False,
    }
