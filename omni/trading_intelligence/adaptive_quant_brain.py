from __future__ import annotations

from dataclasses import asdict
from math import sqrt
from statistics import fmean, pstdev
from typing import Any, Iterable

from omni.trading_intelligence.quant_firm_engine import strategy_votes
from omni.trading_intelligence.chart_pattern_engine import detect_chart_patterns
from omni.trading_intelligence.indicator_plugin_registry import indicator_registry


MIN_BARS = 80


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _series(candles: Iterable[dict[str, Any]], key: str) -> list[float]:
    result: list[float] = []
    for row in candles:
        if row.get(key) is None:
            continue
        try:
            result.append(float(row[key]))
        except (TypeError, ValueError):
            continue
    return result


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    current = fmean(values[:period])
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    alpha = 2.0 / (period + 1.0)
    current = fmean(values[:period])
    out = [current]
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
        out.append(current)
    return out


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(values[-period - 1 : -1], values[-period:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = fmean(gains)
    avg_loss = fmean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    ranges: list[float] = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        high = _f(current.get("high"))
        low = _f(current.get("low"))
        prev_close = _f(previous.get("close"))
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return fmean(ranges) if ranges else None


def _vwap(candles: list[dict[str, Any]], lookback: int = 80) -> float | None:
    weighted = 0.0
    volume_sum = 0.0
    for row in candles[-lookback:]:
        volume = max(_f(row.get("volume")), 0.0)
        typical = (_f(row.get("high")) + _f(row.get("low")) + _f(row.get("close"))) / 3.0
        weighted += typical * volume
        volume_sum += volume
    return weighted / volume_sum if volume_sum > 0 else None


def _macd(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if len(values) < 35:
        return None, None, None
    fast = _ema_series(values, 12)
    slow = _ema_series(values, 26)
    offset = len(fast) - len(slow)
    if offset < 0:
        return None, None, None
    macd_series = [a - b for a, b in zip(fast[offset:], slow)]
    signal = _ema(macd_series, 9)
    if not macd_series or signal is None:
        return None, None, None
    macd = macd_series[-1]
    return macd, signal, macd - signal


def _bollinger(values: list[float], period: int = 20, sigma: float = 2.0) -> tuple[float | None, float | None, float | None]:
    if len(values) < period:
        return None, None, None
    sample = values[-period:]
    mean = fmean(sample)
    sd = pstdev(sample)
    return mean - sigma * sd, mean, mean + sigma * sd


def _stochastic(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period:
        return None
    rows = candles[-period:]
    low = min(_f(row.get("low")) for row in rows)
    high = max(_f(row.get("high")) for row in rows)
    if high <= low:
        return 50.0
    return 100.0 * (_f(rows[-1].get("close")) - low) / (high - low)


def _roc(values: list[float], period: int = 10) -> float | None:
    if len(values) <= period or values[-period - 1] == 0:
        return None
    return ((values[-1] / values[-period - 1]) - 1.0) * 100.0


def _adx(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period + 2:
        return None
    trs: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    rows = candles[-period - 1 :]
    for previous, current in zip(rows[:-1], rows[1:]):
        up = _f(current.get("high")) - _f(previous.get("high"))
        down = _f(previous.get("low")) - _f(current.get("low"))
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        high = _f(current.get("high"))
        low = _f(current.get("low"))
        prev_close = _f(previous.get("close"))
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    atr = fmean(trs) if trs else 0.0
    if atr <= 0:
        return 0.0
    plus_di = 100.0 * fmean(plus_dm) / atr
    minus_di = 100.0 * fmean(minus_dm) / atr
    denom = plus_di + minus_di
    return 100.0 * abs(plus_di - minus_di) / denom if denom else 0.0


def _regime(candles: list[dict[str, Any]], indicators: dict[str, Any]) -> str:
    closes = _series(candles, "close")
    if len(closes) < 55:
        return "INSUFFICIENT_DATA"
    ema20 = indicators.get("ema20")
    ema50 = indicators.get("ema50")
    adx = _f(indicators.get("adx"))
    returns = [(b / a) - 1.0 for a, b in zip(closes[-31:-1], closes[-30:]) if a]
    annualized_vol = pstdev(returns) * sqrt(252.0) if len(returns) > 5 else 0.0
    trend_gap = abs(_f(ema20, closes[-1]) - _f(ema50, closes[-1])) / max(abs(closes[-1]), 1e-9)
    if annualized_vol >= 0.50:
        return "HIGH_VOLATILITY"
    if adx >= 24.0 or trend_gap >= 0.004:
        return "TRENDING"
    return "RANGE"


def indicator_snapshot(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closes = _series(candles, "close")
    volumes = _series(candles, "volume")
    macd, macd_signal, macd_hist = _macd(closes)
    bb_low, bb_mid, bb_high = _bollinger(closes)
    volume_mean = fmean(volumes[-20:]) if len(volumes) >= 20 else None
    return {
        "close": closes[-1] if closes else None,
        "ema9": _ema(closes, 9),
        "ema20": _ema(closes, 20),
        "ema50": _ema(closes, 50),
        "ema200": _ema(closes, 200),
        "rsi14": _rsi(closes, 14),
        "atr14": _atr(candles, 14),
        "vwap": _vwap(candles),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "bb_low": bb_low,
        "bb_mid": bb_mid,
        "bb_high": bb_high,
        "stochastic14": _stochastic(candles, 14),
        "roc10": _roc(closes, 10),
        "adx": _adx(candles, 14),
        "relative_volume": (volumes[-1] / volume_mean) if volumes and volume_mean and volume_mean > 0 else None,
    }


def _swing_points(candles: list[dict[str, Any]], left: int = 2, right: int = 2) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index in range(left, len(candles) - right):
        high = _f(candles[index].get("high"))
        low = _f(candles[index].get("low"))
        if high >= max(_f(candles[j].get("high")) for j in range(index - left, index + right + 1)):
            highs.append((index, high))
        if low <= min(_f(candles[j].get("low")) for j in range(index - left, index + right + 1)):
            lows.append((index, low))
    return highs, lows


def structure_snapshot(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if len(candles) < 10:
        return {"bias": "INSUFFICIENT_DATA", "supports": [], "resistances": [], "patterns": []}
    swings_high, swings_low = _swing_points(candles[-120:])
    close = _f(candles[-1].get("close"))
    support_candidates = sorted({round(value, 10) for _, value in swings_low if value < close}, reverse=True)
    resistance_candidates = sorted({round(value, 10) for _, value in swings_high if value > close})
    supports = support_candidates[:3]
    resistances = resistance_candidates[:3]

    bias = "RANGE"
    if len(swings_high) >= 2 and len(swings_low) >= 2:
        hh = swings_high[-1][1] > swings_high[-2][1]
        hl = swings_low[-1][1] > swings_low[-2][1]
        lh = swings_high[-1][1] < swings_high[-2][1]
        ll = swings_low[-1][1] < swings_low[-2][1]
        if hh and hl:
            bias = "BULLISH"
        elif lh and ll:
            bias = "BEARISH"
        else:
            bias = "MIXED"

    recent_high = max(_f(row.get("high")) for row in candles[-21:-1])
    recent_low = min(_f(row.get("low")) for row in candles[-21:-1])
    bos = "BULLISH" if close > recent_high else "BEARISH" if close < recent_low else "NONE"
    choch = "NONE"
    if bias == "BEARISH" and bos == "BULLISH":
        choch = "BULLISH"
    elif bias == "BULLISH" and bos == "BEARISH":
        choch = "BEARISH"

    fvg: list[dict[str, Any]] = []
    for index in range(max(2, len(candles) - 30), len(candles)):
        a = candles[index - 2]
        c = candles[index]
        if _f(c.get("low")) > _f(a.get("high")):
            fvg.append({"type": "BULLISH", "low": _f(a.get("high")), "high": _f(c.get("low"))})
        elif _f(c.get("high")) < _f(a.get("low")):
            fvg.append({"type": "BEARISH", "low": _f(c.get("high")), "high": _f(a.get("low"))})

    last = candles[-1]
    prior_high = max(_f(row.get("high")) for row in candles[-11:-1])
    prior_low = min(_f(row.get("low")) for row in candles[-11:-1])
    sweep = "NONE"
    if _f(last.get("high")) > prior_high and close < prior_high:
        sweep = "HIGH_SWEEP"
    elif _f(last.get("low")) < prior_low and close > prior_low:
        sweep = "LOW_SWEEP"

    patterns: list[str] = []
    if len(candles) >= 2:
        prev = candles[-2]
        body = abs(_f(last.get("close")) - _f(last.get("open")))
        lower_wick = min(_f(last.get("open")), _f(last.get("close"))) - _f(last.get("low"))
        upper_wick = _f(last.get("high")) - max(_f(last.get("open")), _f(last.get("close")))
        if lower_wick >= max(body * 2.0, 1e-12) and upper_wick <= max(body, 1e-12):
            patterns.append("HAMMER")
        if upper_wick >= max(body * 2.0, 1e-12) and lower_wick <= max(body, 1e-12):
            patterns.append("SHOOTING_STAR")
        if _f(last.get("close")) > _f(last.get("open")) and _f(prev.get("close")) < _f(prev.get("open")):
            if _f(last.get("open")) <= _f(prev.get("close")) and _f(last.get("close")) >= _f(prev.get("open")):
                patterns.append("BULLISH_ENGULFING")
        if _f(last.get("close")) < _f(last.get("open")) and _f(prev.get("close")) > _f(prev.get("open")):
            if _f(last.get("open")) >= _f(prev.get("close")) and _f(last.get("close")) <= _f(prev.get("open")):
                patterns.append("BEARISH_ENGULFING")

    return {
        "bias": bias,
        "bos": bos,
        "choch": choch,
        "supports": supports,
        "resistances": resistances,
        "nearest_support": supports[0] if supports else None,
        "nearest_resistance": resistances[0] if resistances else None,
        "fvg": fvg[-5:],
        "liquidity_sweep": sweep,
        "patterns": patterns,
        "chart_patterns": detect_chart_patterns(candles),
    }


def _learned_family_weights() -> dict[str, float]:
    try:
        from omni.trading_intelligence.trade_learning_engine import learning_engine

        return learning_engine.family_weights()
    except Exception:
        return {}


def _vote(strategy: str, family: str, side: str, score: float, evidence: list[str]) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "family": family,
        "side": side,
        "score": max(0.0, min(float(score), 100.0)),
        "evidence": tuple(evidence),
    }


def _advanced_votes(indicators: dict[str, Any], structure: dict[str, Any]) -> list[dict[str, Any]]:
    votes: list[dict[str, Any]] = []
    close = _f(indicators.get("close"))
    ema20 = indicators.get("ema20")
    ema50 = indicators.get("ema50")
    macd_hist = indicators.get("macd_hist")
    adx = _f(indicators.get("adx"))
    rvol = indicators.get("relative_volume")
    rsi = indicators.get("rsi14")
    bb_low = indicators.get("bb_low")
    bb_high = indicators.get("bb_high")

    if ema20 is not None and ema50 is not None and macd_hist is not None:
        if close > _f(ema20) > _f(ema50) and _f(macd_hist) > 0:
            votes.append(_vote("TREND_MACD_CONFLUENCE", "momentum", "LONG", 74, ["EMA20>EMA50", "MACD histogram positive"]))
        elif close < _f(ema20) < _f(ema50) and _f(macd_hist) < 0:
            votes.append(_vote("TREND_MACD_CONFLUENCE", "momentum", "SHORT", 74, ["EMA20<EMA50", "MACD histogram negative"]))

    if structure.get("bos") == "BULLISH":
        votes.append(_vote("BREAK_OF_STRUCTURE", "structure", "LONG", 72, ["Bullish BOS"]))
    elif structure.get("bos") == "BEARISH":
        votes.append(_vote("BREAK_OF_STRUCTURE", "structure", "SHORT", 72, ["Bearish BOS"]))

    if structure.get("choch") == "BULLISH":
        votes.append(_vote("CHANGE_OF_CHARACTER", "structure", "LONG", 76, ["Bullish CHOCH"]))
    elif structure.get("choch") == "BEARISH":
        votes.append(_vote("CHANGE_OF_CHARACTER", "structure", "SHORT", 76, ["Bearish CHOCH"]))

    if structure.get("liquidity_sweep") == "LOW_SWEEP":
        votes.append(_vote("LIQUIDITY_REVERSAL", "structure", "LONG", 69, ["Prior lows swept and reclaimed"]))
    elif structure.get("liquidity_sweep") == "HIGH_SWEEP":
        votes.append(_vote("LIQUIDITY_REVERSAL", "structure", "SHORT", 69, ["Prior highs swept and rejected"]))

    if rvol is not None and _f(rvol) >= 1.8 and adx >= 20:
        side = "LONG" if _f(macd_hist) >= 0 else "SHORT"
        votes.append(_vote("VOLUME_TREND_EXPANSION", "volume", side, 67, [f"RVOL={_f(rvol):.2f}x", f"ADX={adx:.1f}"]))

    if rsi is not None and bb_low is not None and bb_high is not None:
        if close <= _f(bb_low) and _f(rsi) <= 32:
            votes.append(_vote("BOLLINGER_RSI_EXTREME", "mean_reversion", "LONG", 63, ["Below lower band", f"RSI={_f(rsi):.1f}"]))
        elif close >= _f(bb_high) and _f(rsi) >= 68:
            votes.append(_vote("BOLLINGER_RSI_EXTREME", "mean_reversion", "SHORT", 63, ["Above upper band", f"RSI={_f(rsi):.1f}"]))

    if "BULLISH_ENGULFING" in structure.get("patterns", []):
        votes.append(_vote("CANDLE_PATTERN", "pattern", "LONG", 58, ["Bullish engulfing"]))
    if "BEARISH_ENGULFING" in structure.get("patterns", []):
        votes.append(_vote("CANDLE_PATTERN", "pattern", "SHORT", 58, ["Bearish engulfing"]))

    for pattern in structure.get("chart_patterns") or []:
        bias = str(pattern.get("bias") or "").upper()
        name = str(pattern.get("pattern") or "CHART_PATTERN")
        confidence = float(pattern.get("confidence") or 0.0)
        if bias == "BULLISH":
            votes.append(_vote("HIGHER_ORDER_CHART_PATTERN", "pattern", "LONG", 52 + confidence * 20, [name]))
        elif bias == "BEARISH":
            votes.append(_vote("HIGHER_ORDER_CHART_PATTERN", "pattern", "SHORT", 52 + confidence * 20, [name]))

    return votes


def adaptive_decide(symbol: str, timeframe: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
    if len(candles) < MIN_BARS:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "regime": "INSUFFICIENT_DATA",
            "side": "WAIT",
            "score": 0.0,
            "entry": None,
            "stop": None,
            "target": None,
            "risk_reward": None,
            "votes": [],
            "paper_only": True,
            "live_execution": False,
        }

    indicators = indicator_snapshot(candles)
    structure = structure_snapshot(candles)
    regime = _regime(candles, indicators)

    custom_indicators = indicator_registry.evaluate_all(candles)

    base_votes = [
        {
            "strategy": vote.strategy,
            "family": vote.family,
            "side": vote.side,
            "score": vote.score,
            "evidence": tuple(vote.evidence),
        }
        for vote in strategy_votes(candles)
    ]
    all_votes = base_votes + _advanced_votes(indicators, structure)

    regime_weights = {
        "TRENDING": {"trend": 1.25, "momentum": 1.20, "breakout": 1.15, "structure": 1.15, "volume": 1.05, "pattern": 0.95, "mean_reversion": 0.55},
        "RANGE": {"mean_reversion": 1.25, "structure": 1.10, "pattern": 1.05, "volume": 1.0, "trend": 0.65, "momentum": 0.70, "breakout": 0.70},
        "HIGH_VOLATILITY": {"breakout": 1.20, "structure": 1.20, "momentum": 1.05, "volume": 1.10, "trend": 1.0, "pattern": 0.90, "mean_reversion": 0.55},
    }.get(regime, {})
    learned = _learned_family_weights()

    totals = {"LONG": 0.0, "SHORT": 0.0}
    weights = {"LONG": 0.0, "SHORT": 0.0}
    for vote in all_votes:
        side = str(vote.get("side") or "").upper()
        if side not in totals:
            continue
        family = str(vote.get("family") or "")
        weight = _f(regime_weights.get(family), 1.0) * _f(learned.get(family), 1.0)
        totals[side] += _f(vote.get("score")) * weight
        weights[side] += weight

    long_score = totals["LONG"] / weights["LONG"] if weights["LONG"] else 0.0
    short_score = totals["SHORT"] / weights["SHORT"] if weights["SHORT"] else 0.0
    top_score = max(long_score, short_score)
    side = "WAIT"
    if top_score >= 60.0 and abs(long_score - short_score) >= 7.0:
        side = "LONG" if long_score > short_score else "SHORT"

    entry = _f(indicators.get("close")) if side in {"LONG", "SHORT"} else None
    atr = _f(indicators.get("atr14"))
    stop = target = rr = None
    if entry is not None and atr > 0:
        support = structure.get("nearest_support")
        resistance = structure.get("nearest_resistance")
        if side == "LONG":
            atr_stop = entry - 1.20 * atr
            structure_stop = (_f(support) - 0.20 * atr) if support is not None and _f(support) < entry else atr_stop
            stop = min(atr_stop, structure_stop)
            base_target = entry + 2.40 * atr
            target = max(base_target, _f(resistance)) if resistance is not None and _f(resistance) > entry else base_target
        else:
            atr_stop = entry + 1.20 * atr
            structure_stop = (_f(resistance) + 0.20 * atr) if resistance is not None and _f(resistance) > entry else atr_stop
            stop = max(atr_stop, structure_stop)
            base_target = entry - 2.40 * atr
            target = min(base_target, _f(support)) if support is not None and _f(support) < entry else base_target
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else None

    ranked_votes = sorted(all_votes, key=lambda row: _f(row.get("score")), reverse=True)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "regime": regime,
        "side": side,
        "score": round(top_score, 2),
        "long_score": round(long_score, 2),
        "short_score": round(short_score, 2),
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": rr,
        "votes": ranked_votes,
        "indicators": indicators,
        "structure": structure,
        "learning_weights": learned,
        "confluence_count": len(ranked_votes),
        "custom_indicators": custom_indicators,
        "indicator_plugins": {
            "registered": indicator_registry.describe(),
            "supported": [
                "EMA", "RSI", "ATR", "VWAP", "MACD", "BOLLINGER", "STOCHASTIC", "ROC", "ADX", "RELATIVE_VOLUME"
            ],
            "premium_lock": {
                "status": "DEFINITION_REQUIRED",
                "message": "Premium Lock can be registered once its exact formula or source logic is supplied; JARVIS will not invent proprietary indicator rules.",
            },
        },
        "paper_only": True,
        "live_execution": False,
    }
