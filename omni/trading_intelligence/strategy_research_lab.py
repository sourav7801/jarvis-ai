from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import fmean, pstdev
from typing import Any, Callable

from omni.trading_intelligence.adaptive_quant_brain import indicator_snapshot, structure_snapshot


@dataclass(frozen=True)
class StrategyCandidate:
    name: str
    family: str
    regime: str
    stop_atr: float
    target_atr: float
    minimum_score: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def candidate_library(regime: str) -> list[StrategyCandidate]:
    regime = str(regime or "ANY").upper()
    common = [
        StrategyCandidate(
            "STRUCTURE_MOMENTUM_V1",
            "structure",
            "TRENDING",
            1.20,
            2.40,
            2.0,
            "BOS/CHOCH aligned with EMA trend and MACD momentum.",
        ),
        StrategyCandidate(
            "LIQUIDITY_RECLAIM_V1",
            "structure",
            "RANGE",
            1.00,
            2.00,
            2.0,
            "Liquidity sweep reclaim with RSI/Bollinger confirmation.",
        ),
        StrategyCandidate(
            "VOLATILITY_EXPANSION_V1",
            "breakout",
            "HIGH_VOLATILITY",
            1.35,
            2.70,
            2.0,
            "Break of structure with elevated relative volume and ADX.",
        ),
        StrategyCandidate(
            "VWAP_TREND_PULLBACK_V1",
            "momentum",
            "TRENDING",
            1.10,
            2.20,
            2.0,
            "EMA trend plus VWAP positioning and controlled RSI momentum.",
        ),
        StrategyCandidate(
            "BOLLINGER_MEAN_REVERSION_V1",
            "mean_reversion",
            "RANGE",
            1.00,
            1.80,
            2.0,
            "Bollinger/RSI extreme with nearby structural support or resistance.",
        ),
    ]
    if regime in {"ANY", "UNKNOWN"}:
        return common
    preferred = [candidate for candidate in common if candidate.regime == regime]
    fallback = [candidate for candidate in common if candidate.regime != regime]
    return preferred + fallback


def _signal(candidate: StrategyCandidate, candles: list[dict[str, Any]]) -> tuple[str, float, dict[str, Any]]:
    indicators = indicator_snapshot(candles)
    structure = structure_snapshot(candles)
    close = float(indicators.get("close") or 0.0)
    ema20 = indicators.get("ema20")
    ema50 = indicators.get("ema50")
    vwap = indicators.get("vwap")
    rsi = indicators.get("rsi14")
    macd_hist = indicators.get("macd_hist")
    rvol = indicators.get("relative_volume")
    adx = indicators.get("adx")
    bb_low = indicators.get("bb_low")
    bb_high = indicators.get("bb_high")
    long_points = 0.0
    short_points = 0.0

    if candidate.name == "STRUCTURE_MOMENTUM_V1":
        if structure.get("bos") == "BULLISH" or structure.get("choch") == "BULLISH":
            long_points += 1.0
        if structure.get("bos") == "BEARISH" or structure.get("choch") == "BEARISH":
            short_points += 1.0
        if ema20 is not None and ema50 is not None:
            if close > float(ema20) > float(ema50):
                long_points += 1.0
            elif close < float(ema20) < float(ema50):
                short_points += 1.0
        if macd_hist is not None:
            long_points += 0.75 if float(macd_hist) > 0 else 0.0
            short_points += 0.75 if float(macd_hist) < 0 else 0.0

    elif candidate.name == "LIQUIDITY_RECLAIM_V1":
        sweep = structure.get("liquidity_sweep")
        if sweep == "LOW_SWEEP":
            long_points += 1.25
        elif sweep == "HIGH_SWEEP":
            short_points += 1.25
        if rsi is not None:
            long_points += 0.75 if float(rsi) <= 42 else 0.0
            short_points += 0.75 if float(rsi) >= 58 else 0.0
        if bb_low is not None and close <= float(bb_low) * 1.003:
            long_points += 0.75
        if bb_high is not None and close >= float(bb_high) * 0.997:
            short_points += 0.75

    elif candidate.name == "VOLATILITY_EXPANSION_V1":
        if structure.get("bos") == "BULLISH":
            long_points += 1.0
        elif structure.get("bos") == "BEARISH":
            short_points += 1.0
        if rvol is not None and float(rvol) >= 1.5:
            long_points += 0.5
            short_points += 0.5
        if adx is not None and float(adx) >= 22:
            long_points += 0.5
            short_points += 0.5
        if macd_hist is not None:
            long_points += 0.75 if float(macd_hist) > 0 else 0.0
            short_points += 0.75 if float(macd_hist) < 0 else 0.0

    elif candidate.name == "VWAP_TREND_PULLBACK_V1":
        if ema20 is not None and ema50 is not None and vwap is not None:
            if close > float(ema20) > float(ema50) and close >= float(vwap):
                long_points += 1.5
            if close < float(ema20) < float(ema50) and close <= float(vwap):
                short_points += 1.5
        if rsi is not None:
            if 45 <= float(rsi) <= 66:
                long_points += 0.75
            if 34 <= float(rsi) <= 55:
                short_points += 0.75
        if structure.get("bias") == "BULLISH":
            long_points += 0.5
        elif structure.get("bias") == "BEARISH":
            short_points += 0.5

    elif candidate.name == "BOLLINGER_MEAN_REVERSION_V1":
        if rsi is not None and bb_low is not None and close <= float(bb_low) and float(rsi) <= 32:
            long_points += 1.5
        if rsi is not None and bb_high is not None and close >= float(bb_high) and float(rsi) >= 68:
            short_points += 1.5
        if structure.get("nearest_support") is not None and close >= float(structure["nearest_support"]):
            long_points += 0.5
        if structure.get("nearest_resistance") is not None and close <= float(structure["nearest_resistance"]):
            short_points += 0.5

    side = "WAIT"
    score = max(long_points, short_points)
    if score >= candidate.minimum_score and abs(long_points - short_points) >= 0.5:
        side = "LONG" if long_points > short_points else "SHORT"
    return side, score, {"indicators": indicators, "structure": structure}


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    ranges = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        high = float(current["high"])
        low = float(current["low"])
        previous_close = float(previous["close"])
        ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return fmean(ranges) if ranges else None


def backtest_candidate(
    candles: list[dict[str, Any]],
    candidate: StrategyCandidate,
    *,
    fee_bps: float = 2.0,
    slippage_bps: float = 1.0,
    warmup: int = 80,
) -> dict[str, Any]:
    if len(candles) < warmup + 20:
        return {
            "candidate": candidate.to_dict(),
            "trades": 0,
            "message": "Insufficient bars for research backtest.",
            "research_only": True,
            "live_execution": False,
        }

    trades: list[dict[str, Any]] = []
    index = warmup
    while index < len(candles) - 1:
        history = candles[: index + 1]
        side, signal_score, _context = _signal(candidate, history)
        if side == "WAIT":
            index += 1
            continue
        atr = _atr(history, 14)
        if atr is None or atr <= 0:
            index += 1
            continue

        next_bar = candles[index + 1]
        raw_entry = float(next_bar.get("open") or next_bar["close"])
        slip = raw_entry * (slippage_bps / 10_000.0)
        entry = raw_entry + slip if side == "LONG" else raw_entry - slip
        stop_distance = candidate.stop_atr * atr
        target_distance = candidate.target_atr * atr
        stop = entry - stop_distance if side == "LONG" else entry + stop_distance
        target = entry + target_distance if side == "LONG" else entry - target_distance
        initial_risk = abs(entry - stop)
        exit_price = None
        exit_reason = None
        exit_index = None

        for future_index in range(index + 1, len(candles)):
            bar = candles[future_index]
            high = float(bar["high"])
            low = float(bar["low"])
            if side == "LONG":
                stop_hit = low <= stop
                target_hit = high >= target
                if stop_hit and target_hit:
                    exit_price = stop
                    exit_reason = "STOP_AND_TARGET_SAME_BAR_PESSIMISTIC_STOP"
                elif stop_hit:
                    exit_price = stop
                    exit_reason = "STOP"
                elif target_hit:
                    exit_price = target
                    exit_reason = "TARGET"
            else:
                stop_hit = high >= stop
                target_hit = low <= target
                if stop_hit and target_hit:
                    exit_price = stop
                    exit_reason = "STOP_AND_TARGET_SAME_BAR_PESSIMISTIC_STOP"
                elif stop_hit:
                    exit_price = stop
                    exit_reason = "STOP"
                elif target_hit:
                    exit_price = target
                    exit_reason = "TARGET"
            if exit_price is not None:
                exit_index = future_index
                break
            if future_index - (index + 1) >= 30:
                exit_price = float(bar["close"])
                exit_reason = "TIME_EXIT"
                exit_index = future_index
                break

        if exit_price is None or exit_index is None:
            exit_price = float(candles[-1]["close"])
            exit_reason = "END_OF_DATA"
            exit_index = len(candles) - 1

        gross = (exit_price - entry) if side == "LONG" else (entry - exit_price)
        fees = (abs(entry) + abs(exit_price)) * (fee_bps / 10_000.0)
        net = gross - fees
        r_multiple = net / initial_risk if initial_risk > 0 else 0.0
        trades.append(
            {
                "side": side,
                "entry_index": index + 1,
                "exit_index": exit_index,
                "entry": entry,
                "exit": exit_price,
                "stop": stop,
                "target": target,
                "signal_score": signal_score,
                "r": r_multiple,
                "reason": exit_reason,
            }
        )
        index = max(index + 1, exit_index + 1)

    r_values = [float(trade["r"]) for trade in trades]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    curve = []
    for value in r_values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        curve.append(equity)
    expectancy = fmean(r_values) if r_values else 0.0
    sd = pstdev(r_values) if len(r_values) > 1 else 0.0
    sharpe_like = (expectancy / sd) * sqrt(len(r_values)) if sd > 0 else 0.0
    return {
        "candidate": candidate.to_dict(),
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(trades)) if trades else 0.0,
        "expectancy_r": expectancy,
        "net_r": sum(r_values),
        "avg_win_r": fmean(wins) if wins else 0.0,
        "avg_loss_r": fmean(losses) if losses else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0),
        "max_drawdown_r": max_drawdown,
        "sharpe_like": sharpe_like,
        "equity_curve_r": curve,
        "trade_log": trades,
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "research_only": True,
        "live_execution": False,
    }


def walk_forward_candidate(
    candles: list[dict[str, Any]],
    candidate: StrategyCandidate,
    *,
    folds: int = 3,
) -> dict[str, Any]:
    folds = max(2, min(int(folds), 6))
    if len(candles) < 300:
        return {
            "candidate": candidate.to_dict(),
            "folds": [],
            "passed": False,
            "reason": "INSUFFICIENT_WALK_FORWARD_DATA",
            "research_only": True,
            "live_execution": False,
        }
    segment = len(candles) // folds
    results = []
    for fold in range(folds):
        start = max(0, fold * segment - 100)
        end = len(candles) if fold == folds - 1 else (fold + 1) * segment
        sample = candles[start:end]
        result = backtest_candidate(sample, candidate)
        results.append(
            {
                "fold": fold + 1,
                "bars": len(sample),
                "trades": result.get("trades", 0),
                "expectancy_r": result.get("expectancy_r", 0.0),
                "profit_factor": result.get("profit_factor", 0.0),
                "max_drawdown_r": result.get("max_drawdown_r", 0.0),
                "net_r": result.get("net_r", 0.0),
            }
        )
    usable = [row for row in results if int(row.get("trades") or 0) >= 3]
    positive = [row for row in usable if float(row.get("expectancy_r") or 0.0) > 0 and float(row.get("profit_factor") or 0.0) > 1.0]
    passed = bool(usable and len(positive) >= max(1, len(usable) - 1))
    return {
        "candidate": candidate.to_dict(),
        "folds": results,
        "usable_folds": len(usable),
        "positive_folds": len(positive),
        "passed": passed,
        "research_only": True,
        "live_execution": False,
    }


def research_candidates(
    symbol: str,
    timeframe: str,
    candles: list[dict[str, Any]],
    *,
    regime: str = "ANY",
) -> dict[str, Any]:
    reports = []
    for candidate in candidate_library(regime):
        backtest = backtest_candidate(candles, candidate)
        walk_forward = walk_forward_candidate(candles, candidate)
        trades = int(backtest.get("trades") or 0)
        expectancy = float(backtest.get("expectancy_r") or 0.0)
        profit_factor = float(backtest.get("profit_factor") or 0.0)
        drawdown = float(backtest.get("max_drawdown_r") or 0.0)
        robustness = 1.0 if walk_forward.get("passed") else 0.0
        sample_factor = min(trades / 30.0, 1.0)
        quality = (
            max(min(expectancy, 2.0), -2.0) * 25.0
            + max(min(profit_factor - 1.0, 2.0), -1.0) * 20.0
            + robustness * 25.0
            + sample_factor * 20.0
            - min(drawdown, 10.0) * 2.0
        )
        status = "REJECT"
        if (
            trades >= 20
            and expectancy > 0.05
            and profit_factor >= 1.15
            and walk_forward.get("passed")
            and drawdown <= 8.0
        ):
            status = "PAPER_CHALLENGER"
        reports.append(
            {
                "candidate": candidate.to_dict(),
                "quality_score": round(quality, 2),
                "status": status,
                "backtest": {key: value for key, value in backtest.items() if key not in {"trade_log", "equity_curve_r"}},
                "walk_forward": walk_forward,
            }
        )
    reports.sort(key=lambda row: float(row.get("quality_score") or 0.0), reverse=True)
    return {
        "success": True,
        "symbol": str(symbol).upper(),
        "timeframe": timeframe,
        "candidates": reports,
        "best_candidate": reports[0] if reports else None,
        "governance": {
            "automatic_production_promotion": False,
            "paper_challenger_only": True,
            "requires_out_of_sample_validation": True,
            "requires_minimum_trades": 20,
        },
        "research_only": True,
        "live_execution": False,
    }
