from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from statistics import fmean, pstdev
from typing import Any, Iterable


@dataclass(frozen=True)
class StrategyVote:
    strategy: str
    family: str
    side: str
    score: float
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuantDecision:
    symbol: str
    timeframe: str
    regime: str
    side: str
    score: float
    entry: float | None
    stop: float | None
    target: float | None
    risk_reward: float | None
    votes: tuple[StrategyVote, ...]
    paper_only: bool = True
    live_execution: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["votes"] = [vote.to_dict() for vote in self.votes]
        return value


def _series(candles: Iterable[dict[str, Any]], key: str) -> list[float]:
    return [float(row[key]) for row in candles if row.get(key) is not None]


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    current = fmean(values[:period])
    for value in values[period:]:
        current = alpha * value + (1.0 - alpha) * current
    return current


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
        high = float(current["high"])
        low = float(current["low"])
        prev_close = float(previous["close"])
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return fmean(ranges) if ranges else None


def _vwap(candles: list[dict[str, Any]], lookback: int = 50) -> float | None:
    rows = candles[-lookback:]
    weighted = 0.0
    volume_sum = 0.0
    for row in rows:
        volume = float(row.get("volume") or 0.0)
        typical = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3.0
        weighted += typical * volume
        volume_sum += volume
    return weighted / volume_sum if volume_sum > 0 else None


def _zscore(values: list[float], period: int = 20) -> float | None:
    if len(values) < period:
        return None
    sample = values[-period:]
    sigma = pstdev(sample)
    if sigma == 0:
        return 0.0
    return (sample[-1] - fmean(sample)) / sigma


def _regime(candles: list[dict[str, Any]]) -> str:
    closes = _series(candles, "close")
    if len(closes) < 55:
        return "INSUFFICIENT_DATA"
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    returns = [(b / a) - 1.0 for a, b in zip(closes[-31:-1], closes[-30:]) if a]
    vol = pstdev(returns) * sqrt(252.0) if len(returns) > 5 else 0.0
    trend_gap = abs((ema20 or closes[-1]) - (ema50 or closes[-1])) / max(abs(closes[-1]), 1e-9)
    if vol > 0.45:
        return "HIGH_VOLATILITY"
    if trend_gap > 0.004:
        return "TRENDING"
    return "RANGE"


def _vote(strategy: str, family: str, side: str, score: float, *evidence: str) -> StrategyVote:
    return StrategyVote(strategy, family, side, max(0.0, min(100.0, float(score))), tuple(evidence))


def strategy_votes(candles: list[dict[str, Any]]) -> tuple[StrategyVote, ...]:
    if len(candles) < 60:
        return ()
    closes = _series(candles, "close")
    highs = _series(candles, "high")
    lows = _series(candles, "low")
    volumes = _series(candles, "volume") if any(row.get("volume") is not None for row in candles) else []
    close = closes[-1]
    ema9 = _ema(closes, 9)
    ema20 = _ema(closes, 20)
    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, 50)
    rsi14 = _rsi(closes, 14)
    atr14 = _atr(candles, 14)
    vwap = _vwap(candles)
    z20 = _zscore(closes, 20)
    votes: list[StrategyVote] = []

    if ema9 and ema21:
        side = "LONG" if ema9 > ema21 else "SHORT"
        votes.append(_vote("EMA_9_21_TREND", "trend", side, 62, f"EMA9={ema9:.2f}", f"EMA21={ema21:.2f}"))

    if ema20 and ema50:
        if close > ema20 > ema50:
            votes.append(_vote("EMA_20_50_TREND", "trend", "LONG", 70, "close>EMA20>EMA50"))
        elif close < ema20 < ema50:
            votes.append(_vote("EMA_20_50_TREND", "trend", "SHORT", 70, "close<EMA20<EMA50"))

    if vwap:
        if close > vwap and ema9 and ema21 and ema9 > ema21:
            votes.append(_vote("VWAP_MOMENTUM", "momentum", "LONG", 68, "above VWAP", "EMA momentum bullish"))
        elif close < vwap and ema9 and ema21 and ema9 < ema21:
            votes.append(_vote("VWAP_MOMENTUM", "momentum", "SHORT", 68, "below VWAP", "EMA momentum bearish"))

    if rsi14 is not None and vwap:
        if rsi14 < 30 and close < vwap:
            votes.append(_vote("RSI_VWAP_MEAN_REVERSION", "mean_reversion", "LONG", 60, f"RSI={rsi14:.1f}", "below VWAP"))
        elif rsi14 > 70 and close > vwap:
            votes.append(_vote("RSI_VWAP_MEAN_REVERSION", "mean_reversion", "SHORT", 60, f"RSI={rsi14:.1f}", "above VWAP"))

    lookback_high = max(highs[-21:-1])
    lookback_low = min(lows[-21:-1])
    if close > lookback_high:
        votes.append(_vote("DONCHIAN_BREAKOUT_20", "breakout", "LONG", 72, "20-bar breakout"))
    elif close < lookback_low:
        votes.append(_vote("DONCHIAN_BREAKOUT_20", "breakout", "SHORT", 72, "20-bar breakdown"))

    first_range = candles[-30:-24]
    if first_range:
        orb_high = max(float(row["high"]) for row in first_range)
        orb_low = min(float(row["low"]) for row in first_range)
        if close > orb_high:
            votes.append(_vote("OPENING_RANGE_BREAKOUT_PROXY", "breakout", "LONG", 64, "above recent opening-range proxy"))
        elif close < orb_low:
            votes.append(_vote("OPENING_RANGE_BREAKOUT_PROXY", "breakout", "SHORT", 64, "below recent opening-range proxy"))

    if z20 is not None:
        if z20 <= -2.0:
            votes.append(_vote("ZSCORE_REVERSION_20", "mean_reversion", "LONG", 58, f"z20={z20:.2f}"))
        elif z20 >= 2.0:
            votes.append(_vote("ZSCORE_REVERSION_20", "mean_reversion", "SHORT", 58, f"z20={z20:.2f}"))

    if len(candles) >= 4:
        a, b, c = candles[-3], candles[-2], candles[-1]
        bullish_fvg = float(c["low"]) > float(a["high"])
        bearish_fvg = float(c["high"]) < float(a["low"])
        if bullish_fvg:
            votes.append(_vote("FAIR_VALUE_GAP", "structure", "LONG", 55, "bullish three-candle imbalance"))
        if bearish_fvg:
            votes.append(_vote("FAIR_VALUE_GAP", "structure", "SHORT", 55, "bearish three-candle imbalance"))

    previous_high = max(highs[-11:-1])
    previous_low = min(lows[-11:-1])
    if float(candles[-1]["high"]) > previous_high and close < previous_high:
        votes.append(_vote("LIQUIDITY_SWEEP", "structure", "SHORT", 58, "swept prior highs and closed back below"))
    if float(candles[-1]["low"]) < previous_low and close > previous_low:
        votes.append(_vote("LIQUIDITY_SWEEP", "structure", "LONG", 58, "swept prior lows and closed back above"))

    if volumes and len(volumes) >= 20:
        mean_volume = fmean(volumes[-20:])
        if mean_volume > 0 and volumes[-1] / mean_volume >= 1.8:
            side = "LONG" if candles[-1]["close"] >= candles[-1]["open"] else "SHORT"
            votes.append(_vote("RELATIVE_VOLUME_EXPANSION", "volume", side, 56, f"RVOL={volumes[-1]/mean_volume:.2f}x"))

    if atr14 and ema20:
        distance = abs(close - ema20) / atr14
        if distance >= 2.5:
            side = "SHORT" if close > ema20 else "LONG"
            votes.append(_vote("ATR_STRETCH_REVERSION", "mean_reversion", side, 54, f"EMA20 distance={distance:.2f} ATR"))

    return tuple(votes)


def decide(symbol: str, timeframe: str, candles: list[dict[str, Any]]) -> QuantDecision:
    votes = strategy_votes(candles)
    regime = _regime(candles)
    if not votes:
        return QuantDecision(symbol, timeframe, regime, "WAIT", 0.0, None, None, None, None, ())

    regime_family_weight = {
        "TRENDING": {"trend": 1.25, "momentum": 1.20, "breakout": 1.15, "structure": 1.0, "volume": 1.0, "mean_reversion": 0.55},
        "RANGE": {"mean_reversion": 1.25, "structure": 1.10, "volume": 1.0, "trend": 0.65, "momentum": 0.70, "breakout": 0.70},
        "HIGH_VOLATILITY": {"breakout": 1.20, "structure": 1.15, "momentum": 1.05, "trend": 1.0, "volume": 1.05, "mean_reversion": 0.60},
    }.get(regime, {})

    long_score = 0.0
    short_score = 0.0
    long_weight = 0.0
    short_weight = 0.0
    for vote in votes:
        weight = float(regime_family_weight.get(vote.family, 1.0))
        if vote.side == "LONG":
            long_score += vote.score * weight
            long_weight += weight
        elif vote.side == "SHORT":
            short_score += vote.score * weight
            short_weight += weight

    long_avg = long_score / long_weight if long_weight else 0.0
    short_avg = short_score / short_weight if short_weight else 0.0
    side = "WAIT"
    score = max(long_avg, short_avg)
    if abs(long_avg - short_avg) >= 8 and score >= 58:
        side = "LONG" if long_avg > short_avg else "SHORT"

    entry = stop = target = rr = None
    atr14 = _atr(candles, 14)
    if side in {"LONG", "SHORT"} and atr14:
        entry = float(candles[-1]["close"])
        stop_distance = 1.25 * atr14
        target_distance = 2.5 * atr14
        if side == "LONG":
            stop = entry - stop_distance
            target = entry + target_distance
        else:
            stop = entry + stop_distance
            target = entry - target_distance
        rr = target_distance / stop_distance

    return QuantDecision(symbol, timeframe, regime, side, round(score, 2), entry, stop, target, rr, votes)


def position_size(equity: float, entry: float, stop: float, risk_fraction: float = 0.005, max_notional_fraction: float = 0.20) -> int:
    equity = float(equity)
    entry = float(entry)
    stop = float(stop)
    per_unit_risk = abs(entry - stop)
    if equity <= 0 or entry <= 0 or per_unit_risk <= 0:
        return 0
    risk_budget = equity * max(0.0, min(float(risk_fraction), 0.02))
    by_risk = int(risk_budget // per_unit_risk)
    by_notional = int((equity * max_notional_fraction) // entry)
    return max(0, min(by_risk, by_notional))


def select_option_candidate(chain: Iterable[dict[str, Any]], bias: str, underlying_price: float) -> dict[str, Any] | None:
    side = str(bias or "").upper()
    option_type = "CE" if side in {"LONG", "BULLISH", "CALL"} else "PE" if side in {"SHORT", "BEARISH", "PUT"} else ""
    if not option_type:
        return None
    rows = []
    for row in chain:
        kind = str(row.get("option_type") or row.get("type") or "").upper()
        if kind not in {option_type, "CALL" if option_type == "CE" else "PUT"}:
            continue
        try:
            strike = float(row.get("strike") or row.get("strike_price"))
        except (TypeError, ValueError):
            continue
        bid = float(row.get("bid") or row.get("best_bid") or 0.0)
        ask = float(row.get("ask") or row.get("best_ask") or 0.0)
        ltp = float(row.get("ltp") or row.get("last_price") or 0.0)
        volume = float(row.get("volume") or 0.0)
        oi = float(row.get("oi") or row.get("open_interest") or 0.0)
        spread = (ask - bid) if ask > 0 and bid > 0 else max(ltp * 0.02, 0.01)
        distance = abs(strike - float(underlying_price)) / max(float(underlying_price), 1e-9)
        liquidity = (volume + sqrt(max(oi, 0.0))) / max(spread, 0.01)
        rows.append((distance, -liquidity, row))
    if not rows:
        return None
    rows.sort(key=lambda item: (item[0], item[1]))
    selected = dict(rows[0][2])
    selected["selection_reason"] = "near-ATM liquid option candidate for paper research"
    selected["paper_only"] = True
    selected["live_execution"] = False
    return selected
