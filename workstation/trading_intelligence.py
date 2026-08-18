"""Read-only, multi-timeframe market intelligence backed by broker OHLCV data."""

from __future__ import annotations

import math
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from agents.fyers_data_adapter import get_intraday_data
from agents.pattern_engine import analyze_patterns


ALLOWED_SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
TIMEFRAMES = ("5m", "15m", "1h")
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LOCK = threading.RLock()
CACHE_TTL_SECONDS = 45.0
MIN_RISK_REWARD = 1.8


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _round(value: Any, digits: int = 2) -> float:
    return round(_finite(value), digits)


def _rsi(close, period: int = 14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative = gain / loss.replace(0, float("nan"))
    value = 100 - (100 / (1 + relative))
    value = value.where(loss != 0, 100.0)
    value = value.where((gain != 0) | (loss != 0), 50.0)
    return value.fillna(50.0)


def _pattern_evidence(frame) -> dict[str, Any]:
    """Extract recent chart evidence without returning the engine's DataFrame."""

    try:
        analysis = analyze_patterns(frame.tail(180))
    except Exception:
        analysis = {"success": False}
    if not analysis.get("success"):
        return {"patterns": [], "bias": "NEUTRAL", "breakout": "NONE"}
    bars = int(analysis.get("bars") or 0)
    recent: list[dict[str, Any]] = []
    for item in analysis.get("chart_patterns") or []:
        index = item.get("index", item.get("second_index", -1))
        try:
            is_recent = int(index) >= bars - 20
        except (TypeError, ValueError):
            is_recent = False
        if is_recent:
            recent.append(item)
    breakout = str((analysis.get("breakout") or {}).get("signal") or "NONE")
    patterns = [str(item.get("pattern")) for item in recent if item.get("pattern")]
    if breakout != "NONE":
        patterns.insert(0, breakout)
    return {
        "patterns": list(dict.fromkeys(patterns))[:8],
        "bias": str(analysis.get("bias") or "NEUTRAL"),
        "breakout": breakout,
    }


def _frame_analysis(frame, timeframe: str) -> dict[str, Any]:
    required = {"Open", "High", "Low", "Close", "Volume"}
    if frame is None or len(frame) < 60 or not required.issubset(frame.columns):
        raise ValueError(f"{timeframe} requires at least 60 complete OHLCV candles.")
    work = frame.copy()
    for name in required:
        work[name] = work[name].astype(float)
    close = work["Close"]
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    rsi14 = _rsi(close)
    previous = close.shift(1)
    true_range = (
        (work["High"] - work["Low"])
        .to_frame("a")
        .join((work["High"] - previous).abs().rename("b"))
        .join((work["Low"] - previous).abs().rename("c"))
        .max(axis=1)
    )
    atr14 = true_range.ewm(alpha=1 / 14, adjust=False).mean()
    mean20 = close.rolling(20).mean()
    deviation20 = close.rolling(20).std(ddof=0)
    upper_band = mean20 + 2 * deviation20
    lower_band = mean20 - 2 * deviation20

    last = _finite(close.iloc[-1])
    e20 = _finite(ema20.iloc[-1])
    e50 = _finite(ema50.iloc[-1])
    rsi = _finite(rsi14.iloc[-1], 50.0)
    atr = _finite(atr14.iloc[-1])
    slope = _finite((ema20.iloc[-1] / ema20.iloc[-6] - 1) * 100) if _finite(ema20.iloc[-6]) else 0.0
    distance20 = ((last / e20) - 1) * 100 if e20 else 0.0
    distance50 = ((last / e50) - 1) * 100 if e50 else 0.0

    if last > e20 > e50 and rsi >= 52 and slope > 0:
        regime, direction = "TRENDING_UP", "LONG"
    elif last < e20 < e50 and rsi <= 48 and slope < 0:
        regime, direction = "TRENDING_DOWN", "SHORT"
    else:
        regime, direction = "RANGE_OR_TRANSITION", "NEUTRAL"

    directional_score = 50.0
    directional_score += max(min(distance20 * 12, 14), -14)
    directional_score += max(min(distance50 * 7, 14), -14)
    directional_score += max(min((rsi - 50) * 0.55, 14), -14)
    directional_score += max(min(slope * 16, 8), -8)
    directional_score = max(min(directional_score, 100), 0)

    recent = work.tail(20)
    average_volume = _finite(work["Volume"].tail(20).mean())
    volume_ratio = _finite(work["Volume"].iloc[-1] / average_volume, 0.0) if average_volume else 0.0
    pattern = _pattern_evidence(work)
    candidates: list[dict[str, Any]] = []
    if direction in {"LONG", "SHORT"}:
        trend_strength = abs(directional_score - 50)
        candidates.append(
            {
                "strategy": "TREND_FOLLOWING",
                "direction": direction,
                "score": min(92.0, 70.0 + trend_strength * 0.42 + min(volume_ratio, 2.0) * 2),
                "reason": f"EMA20/EMA50 trend, RSI {rsi:.1f}, EMA slope {slope:.3f}%.",
            }
        )
    breakout = pattern["breakout"]
    if breakout in {"BULLISH_BREAKOUT", "BEARISH_BREAKDOWN"}:
        candidates.append(
            {
                "strategy": "BREAKOUT",
                "direction": "LONG" if breakout == "BULLISH_BREAKOUT" else "SHORT",
                "score": 82.0 if volume_ratio >= 1.2 else 74.0,
                "reason": f"{breakout.replace('_', ' ').title()} with {volume_ratio:.2f}x volume.",
            }
        )
    upper = _finite(upper_band.iloc[-1])
    lower = _finite(lower_band.iloc[-1])
    if last < lower and rsi <= 32:
        candidates.append(
            {"strategy": "MEAN_REVERSION", "direction": "LONG", "score": 76.0,
             "reason": f"Close below lower volatility band with RSI {rsi:.1f}."}
        )
    elif last > upper and rsi >= 68:
        candidates.append(
            {"strategy": "MEAN_REVERSION", "direction": "SHORT", "score": 76.0,
             "reason": f"Close above upper volatility band with RSI {rsi:.1f}."}
        )
    directional_patterns = [
        item for item in pattern["patterns"]
        if any(term in item for term in ("BULLISH", "BEARISH", "HAMMER", "SHOOTING_STAR", "DOUBLE_"))
    ]
    if directional_patterns:
        bullish = sum("BULLISH" in item or item in {"HAMMER", "DOUBLE_BOTTOM"} for item in directional_patterns)
        bearish = sum("BEARISH" in item or item in {"SHOOTING_STAR", "DOUBLE_TOP"} for item in directional_patterns)
        pattern_direction = "LONG" if bullish > bearish else "SHORT" if bearish > bullish else ""
        bias_ok = pattern["bias"] in {"NEUTRAL", "BULLISH" if pattern_direction == "LONG" else "BEARISH"}
        if pattern_direction and bias_ok:
            candidates.append(
                {"strategy": "CHART_PATTERN", "direction": pattern_direction, "score": 72.0,
                 "reason": "Recent pattern confirmation: " + ", ".join(directional_patterns[:3]) + "."}
            )
    selected = max(candidates, key=lambda item: item["score"]) if candidates else {
        "strategy": "NO_EDGE", "direction": "NEUTRAL", "score": 0.0,
        "reason": "No strategy passed the deterministic evidence gate.",
    }
    direction = selected["direction"]
    if direction == "LONG":
        regime = "TRENDING_UP" if selected["strategy"] == "TREND_FOLLOWING" else "BULLISH_SETUP"
    elif direction == "SHORT":
        regime = "TRENDING_DOWN" if selected["strategy"] == "TREND_FOLLOWING" else "BEARISH_SETUP"
    else:
        regime = "RANGE_OR_TRANSITION"
    timestamp = work.index[-1]
    return {
        "timeframe": timeframe,
        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        "bars": len(work),
        "price": _round(last),
        "ema20": _round(e20),
        "ema50": _round(e50),
        "rsi14": _round(rsi, 1),
        "atr14": _round(atr),
        "atr_percent": _round(atr / last * 100 if last else 0, 3),
        "ema20_slope_percent": _round(slope, 3),
        "support": _round(recent["Low"].min()),
        "resistance": _round(recent["High"].max()),
        "volume_ratio": _round(volume_ratio, 2),
        "volatility_upper": _round(upper),
        "volatility_lower": _round(lower),
        "regime": regime,
        "direction": direction,
        "directional_score": _round(directional_score, 1),
        "strategy": selected["strategy"],
        "strategy_score": _round(selected["score"], 1),
        "strategy_reason": selected["reason"],
        "chart_patterns": pattern["patterns"],
        "pattern_bias": pattern["bias"],
        "breakout": breakout,
    }


def _synthesize(symbol: str, frames: list[dict[str, Any]], qualities: list[str]) -> dict[str, Any]:
    directions = [item["direction"] for item in frames]
    long_count = directions.count("LONG")
    short_count = directions.count("SHORT")
    dominant = "LONG" if long_count > short_count else "SHORT" if short_count > long_count else "NEUTRAL"
    aligned = max(long_count, short_count)
    if aligned == len(TIMEFRAMES) and len(frames) == len(TIMEFRAMES):
        confidence = 84
    elif aligned >= 2:
        confidence = 68
    elif aligned == 1:
        confidence = 48
    else:
        confidence = 30
    if len(frames) < len(TIMEFRAMES):
        confidence = max(confidence - 15, 15)

    average_score = sum(item["directional_score"] for item in frames) / len(frames)
    momentum = average_score if dominant != "SHORT" else 100 - average_score
    if dominant == "NEUTRAL":
        momentum = 50 - abs(average_score - 50) / 2

    anchor = next((item for item in frames if item["timeframe"] == "15m"), frames[0])
    strategy_votes = Counter(
        item["strategy"] for item in frames
        if item.get("direction") == dominant and item.get("strategy") != "NO_EDGE"
    )
    strategy = strategy_votes.most_common(1)[0][0] if strategy_votes else "NO_EDGE"
    strategy_score = sum(_finite(item.get("strategy_score")) for item in frames) / len(frames)
    chart_patterns = list(dict.fromkeys(
        pattern for item in frames for pattern in (item.get("chart_patterns") or [])
    ))[:10]
    entry = _finite(anchor.get("price"))
    atr = _finite(anchor.get("atr14"))
    stop_distance = atr * 1.5 if atr > 0 else 0.0
    reward_distance = stop_distance * 2.2
    stop_loss = None
    take_profit = None
    risk_reward = 0.0
    if dominant == "LONG" and stop_distance > 0:
        stop_loss = entry - stop_distance
        take_profit = entry + reward_distance
        risk_reward = reward_distance / stop_distance
    elif dominant == "SHORT" and stop_distance > 0:
        stop_loss = entry + stop_distance
        take_profit = entry - reward_distance
        risk_reward = reward_distance / stop_distance

    setup = "NO_QUALIFIED_SETUP"
    gate_reasons: list[str] = []
    if len(frames) != len(TIMEFRAMES) or aligned != len(TIMEFRAMES):
        gate_reasons.append("All three timeframes must agree.")
    if strategy_score < 70:
        gate_reasons.append("Strategy evidence score is below 70.")
    if risk_reward < MIN_RISK_REWARD:
        gate_reasons.append(f"Projected risk/reward is below {MIN_RISK_REWARD:.1f}.")
    if not gate_reasons and confidence >= 80 and dominant in {"LONG", "SHORT"}:
        setup = f"PAPER_WATCH_{dominant}"
        gate_reasons.append("Qualified for the synthetic paper-execution gate.")
    agreement = ", ".join(f"{item['timeframe']} {item['regime']}" for item in frames)
    return {
        "success": True,
        "symbol": symbol,
        "mode": "RESEARCH_AND_PAPER_ONLY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regime": dominant if aligned >= 2 else "MIXED",
        "setup": setup,
        "confidence": confidence,
        "confidence_label": "TIMEFRAME_ALIGNMENT_CONFIDENCE_NOT_WIN_PROBABILITY",
        "momentum": _round(momentum, 1),
        "price": anchor["price"],
        "support": anchor["support"],
        "resistance": anchor["resistance"],
        "atr14": anchor["atr14"],
        "entry": _round(entry),
        "stop_loss": _round(stop_loss) if stop_loss is not None else None,
        "take_profit": _round(take_profit) if take_profit is not None else None,
        "risk_reward": _round(risk_reward, 2),
        "minimum_risk_reward": MIN_RISK_REWARD,
        "strategy": strategy,
        "strategy_score": _round(strategy_score, 1),
        "chart_patterns": chart_patterns,
        "decision_gate": "QUALIFIED" if setup != "NO_QUALIFIED_SETUP" else "WAIT",
        "decision_reasons": gate_reasons,
        "data_quality": sorted(set(qualities)),
        "timeframes": frames,
        "explanation": f"{aligned} of {len(frames)} available timeframes align {dominant}. {agreement}.",
        "risk_notice": "Research output only. It is not a trade instruction, win probability, or authorization to place an order. Live execution is disabled.",
    }


def analyze_symbol(
    symbol: str,
    *,
    loader: Callable[..., dict[str, Any]] = get_intraday_data,
    use_cache: bool = True,
) -> dict[str, Any]:
    requested = str(symbol or "").strip().upper().replace(" ", "")
    if requested not in ALLOWED_SYMBOLS:
        raise ValueError("Trading intelligence supports NIFTY, BANKNIFTY, and SENSEX.")
    return analyze_market_asset(
        requested,
        loader=loader,
        use_cache=use_cache,
        provider_label="FYERS",
    )


def analyze_market_asset(
    symbol: str,
    *,
    loader: Callable[..., dict[str, Any]],
    use_cache: bool = True,
    provider_label: str = "MARKET_DATA",
) -> dict[str, Any]:
    """Analyze any validated asset supplied by a read-only OHLCV loader."""

    requested = str(symbol or "").strip().upper().replace(" ", "")
    if not requested:
        raise ValueError("Market asset is required.")
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(requested)
        if use_cache and cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    analyses: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    qualities: list[str] = []
    for timeframe in TIMEFRAMES:
        try:
            result = loader(requested, timeframe=timeframe, bars=240)
            if not result.get("success"):
                raise ValueError(str(result.get("message") or "Broker data unavailable."))
            analyses.append(_frame_analysis(result.get("data"), timeframe))
            qualities.append(str(result.get("data_quality") or "BROKER_HISTORICAL"))
        except Exception as error:
            errors.append({"timeframe": timeframe, "error": str(error)[:240]})

    if not analyses:
        return {
            "success": False,
            "symbol": requested,
            "mode": "RESEARCH_AND_PAPER_ONLY",
            "timeframes": [],
            "errors": errors,
            "message": f"No valid {provider_label} timeframe data was available for analysis.",
            "risk_notice": "Live execution is disabled.",
        }
    payload = _synthesize(requested, analyses, qualities)
    payload["errors"] = errors
    with _LOCK:
        _CACHE[requested] = (now, payload)
    return payload
