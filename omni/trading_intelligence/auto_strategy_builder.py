"""Governed, data-first automatic strategy research for JARVIS.

Generates explainable strategy candidates from OHLCV history, evaluates them
chronologically with configurable costs, and returns a paper-only proposal.
It never places broker orders, changes production strategy code, or promises
future returns.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable
import math


@dataclass(frozen=True)
class StrategySpec:
    name: str
    family: str
    parameters: dict[str, Any]
    description: str


@dataclass
class BacktestMetrics:
    bars: int = 0
    trades: int = 0
    win_rate: float = 0.0
    net_return_pct: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    expectancy_pct: float = 0.0
    cost_per_turn_pct: float = 0.0


def _num(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _ema(xs: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(xs)
    if len(xs) < period:
        return out
    alpha = 2.0 / (period + 1)
    value = sum(xs[:period]) / period
    out[period - 1] = value
    for i in range(period, len(xs)):
        value = alpha * xs[i] + (1 - alpha) * value
        out[i] = value
    return out


def _rsi(xs: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(xs)
    for i in range(period, len(xs)):
        changes = [xs[j] - xs[j - 1] for j in range(i - period + 1, i + 1)]
        gains = sum(max(0.0, d) for d in changes) / period
        losses = sum(max(0.0, -d) for d in changes) / period
        out[i] = 100.0 if losses == 0 and gains else 50.0 if losses == 0 else 100 - 100 / (1 + gains / losses)
    return out


def candidate_specs() -> list[StrategySpec]:
    """Small, interpretable search space; intentionally not an unbounded optimizer."""
    return [
        StrategySpec("EMA Trend 9/21", "trend", {"fast": 9, "slow": 21}, "Long when EMA9 > EMA21; otherwise flat."),
        StrategySpec("EMA Trend 20/50", "trend", {"fast": 20, "slow": 50}, "Long when EMA20 > EMA50; otherwise flat."),
        StrategySpec("RSI Pullback", "mean_reversion", {"period": 14, "entry": 30, "exit": 55}, "Enter after oversold RSI; exit on recovery."),
        StrategySpec("Donchian Breakout", "breakout", {"lookback": 20}, "Enter long on a close above the prior lookback high; exit below the prior low."),
        StrategySpec("RSI Momentum", "momentum", {"period": 14, "entry": 55, "exit": 45}, "Long above RSI 55; flat below RSI 45."),
    ]


def _signals(spec: StrategySpec, closes: list[float], highs: list[float], lows: list[float]) -> list[int]:
    n = len(closes)
    out = [0] * n
    p = spec.parameters
    if spec.family == "trend":
        fast, slow = _ema(closes, int(p["fast"])), _ema(closes, int(p["slow"]))
        for i in range(n):
            if fast[i] is not None and slow[i] is not None:
                out[i] = 1 if fast[i] > slow[i] else 0
    elif spec.family in ("mean_reversion", "momentum"):
        rsis = _rsi(closes, int(p["period"]))
        position = 0
        for i, rsi in enumerate(rsis):
            if rsi is None:
                out[i] = 0
                continue
            if spec.family == "mean_reversion":
                if rsi <= p["entry"]:
                    position = 1
                elif rsi >= p["exit"]:
                    position = 0
            else:
                if rsi >= p["entry"]:
                    position = 1
                elif rsi <= p["exit"]:
                    position = 0
            out[i] = position
    elif spec.family == "breakout":
        lookback = int(p["lookback"])
        position = 0
        for i in range(n):
            if i >= lookback:
                prior_high = max(highs[i - lookback:i])
                prior_low = min(lows[i - lookback:i])
                if closes[i] > prior_high:
                    position = 1
                elif closes[i] < prior_low:
                    position = 0
            out[i] = position
    return out


def backtest(
    candles: Iterable[dict[str, Any]],
    spec: StrategySpec,
    *,
    cost_per_turn_pct: float = 0.10,
    slippage_per_turn_pct: float = 0.05,
    start: int = 0,
    end: int | None = None,
) -> dict[str, Any]:
    """Evaluate a close-to-close long/flat strategy over [start, end).

    Signals are calculated on the full chronological series for indicator warm-up.
    The signal from bar t is applied only to the return ending at bar t+1.
    Trade statistics count completed position round trips, not signal flips or
    profitable individual bars.
    """
    rows = []
    for row in candles:
        if not isinstance(row, dict):
            continue
        close, high, low = _num(row.get("close")), _num(row.get("high")), _num(row.get("low"))
        if close is not None and high is not None and low is not None and close > 0 and high >= low:
            rows.append({"close": close, "high": high, "low": low})
    closes = [r["close"] for r in rows]
    if end is None:
        end = len(rows)
    end = max(0, min(int(end), len(rows)))
    start = max(0, min(int(start), end))
    cost_inputs = (_num(cost_per_turn_pct), _num(slippage_per_turn_pct))
    if any(v is None or v < 0 for v in cost_inputs):
        return {"ready": False, "reason": "INVALID_COST_ASSUMPTION", "metrics": asdict(BacktestMetrics())}
    cost = float(cost_inputs[0]) + float(cost_inputs[1])
    if end - start < 3:
        return {"ready": False, "reason": "INSUFFICIENT_EVALUATION_BARS", "metrics": asdict(BacktestMetrics(cost_per_turn_pct=cost))}
    signals = _signals(spec, closes, [r["high"] for r in rows], [r["low"] for r in rows])
    equity, peak, max_dd = 1.0, 1.0, 0.0
    returns: list[float] = []
    completed_trades: list[float] = []
    trade_equity: float | None = None
    previous_position = 0
    for i in range(max(start + 1, 1), end):
        position = signals[i - 1]
        gross = position * (closes[i] / closes[i - 1] - 1.0) * 100.0
        turn = abs(position - previous_position)
        net = gross - cost * turn
        returns.append(net)
        equity *= max(0.000001, 1 + net / 100.0)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        if position == 1 and previous_position == 0:
            trade_equity = 1.0
        if trade_equity is not None:
            trade_equity *= max(0.000001, 1 + net / 100.0)
        if position == 0 and previous_position == 1 and trade_equity is not None:
            completed_trades.append((trade_equity - 1.0) * 100.0)
            trade_equity = None
        previous_position = position
    gains = sum(x for x in completed_trades if x > 0)
    losses = -sum(x for x in completed_trades if x < 0)
    metrics = BacktestMetrics(
        bars=len(returns),
        trades=len(completed_trades),
        win_rate=(sum(1 for x in completed_trades if x > 0) / len(completed_trades) * 100.0) if completed_trades else 0.0,
        net_return_pct=(equity - 1.0) * 100.0,
        profit_factor=(gains / losses if losses > 0 else (999.0 if gains > 0 else 0.0)),
        max_drawdown_pct=max_dd,
        expectancy_pct=(sum(completed_trades) / len(completed_trades)) if completed_trades else 0.0,
        cost_per_turn_pct=cost,
    )
    return {"ready": True, "metrics": asdict(metrics)}

def build_strategy_report(
    candles: Iterable[dict[str, Any]],
    *,
    cost_per_turn_pct: float = 0.10,
    slippage_per_turn_pct: float = 0.05,
    minimum_train_bars: int = 120,
    minimum_test_bars: int = 40,
    max_drawdown_pct: float = 12.0,
) -> dict[str, Any]:
    """Rank candidates by out-of-sample metrics and gate them for paper trial."""
    cost_value, slippage_value, drawdown_limit = (
        _num(cost_per_turn_pct), _num(slippage_per_turn_pct), _num(max_drawdown_pct)
    )
    if cost_value is None or slippage_value is None or cost_value < 0 or slippage_value < 0:
        raise ValueError("Cost and slippage assumptions must be finite, non-negative percentages.")
    if drawdown_limit is None or drawdown_limit <= 0 or drawdown_limit > 100:
        raise ValueError("max_drawdown_pct must be greater than 0 and at most 100.")
    if minimum_train_bars < 50 or minimum_test_bars < 20:
        raise ValueError("minimum_train_bars must be >= 50 and minimum_test_bars must be >= 20.")
    cost_per_turn_pct, slippage_per_turn_pct, max_drawdown_pct = cost_value, slippage_value, drawdown_limit
    rows = []
    for row in candles:
        if not isinstance(row, dict):
            continue
        close, high, low = _num(row.get("close")), _num(row.get("high")), _num(row.get("low"))
        if close is not None and high is not None and low is not None and close > 0:
            rows.append({"close": close, "high": high, "low": low})
    n = len(rows)
    if n < minimum_train_bars + minimum_test_bars:
        return {
            "success": False, "state": "INSUFFICIENT_DATA", "bars": n, "candidates": [],
            "message": f"Need at least {minimum_train_bars + minimum_test_bars} valid OHLC bars for chronological train/test validation.",
            "paper_only": True, "live_execution": False,
        }
    split = int(n * 0.70)
    split = max(minimum_train_bars, min(split, n - minimum_test_bars))
    results = []
    for spec in candidate_specs():
        train = backtest(rows, spec, cost_per_turn_pct=cost_per_turn_pct, slippage_per_turn_pct=slippage_per_turn_pct, start=0, end=split)
        test = backtest(rows, spec, cost_per_turn_pct=cost_per_turn_pct, slippage_per_turn_pct=slippage_per_turn_pct, start=split, end=n)
        tm, om = train["metrics"], test["metrics"]
        # Expanding-window checks inside the training segment; the final holdout
        # is kept separate from these stability checks.
        wf_results = []
        remaining = split - minimum_train_bars
        fold_width = remaining // 2
        if fold_width >= minimum_test_bars:
            for fold_index in range(2):
                fold_start = minimum_train_bars + fold_index * fold_width
                fold_end = split if fold_index == 1 else fold_start + fold_width
                fold = backtest(rows, spec, cost_per_turn_pct=cost_per_turn_pct, slippage_per_turn_pct=slippage_per_turn_pct, start=fold_start, end=fold_end)
                wf_results.append({
                    "fold": fold_index + 1,
                    "start_index": fold_start,
                    "end_index": fold_end,
                    "metrics": fold.get("metrics"),
                    "ready": bool(fold.get("ready")),
                })
        wf_positive = sum(1 for fold in wf_results if fold["ready"] and fold["metrics"]["net_return_pct"] > 0)
        wf_pass = len(wf_results) == 2 and wf_positive == 2
        reasons = []
        if not train.get("ready"):
            reasons.append("TRAIN_WINDOW_NOT_READY")
        if not test.get("ready"):
            reasons.append("OUT_OF_SAMPLE_WINDOW_NOT_READY")
        if tm["trades"] < 3:
            reasons.append("INSUFFICIENT_TRAIN_ROUND_TRIPS")
        if om["trades"] < 3:
            reasons.append("INSUFFICIENT_OUT_OF_SAMPLE_ROUND_TRIPS")
        if tm["net_return_pct"] <= 0:
            reasons.append("TRAIN_RETURN_NOT_POSITIVE")
        if om["net_return_pct"] <= 0:
            reasons.append("OUT_OF_SAMPLE_RETURN_NOT_POSITIVE")
        if om["profit_factor"] < 1.10:
            reasons.append("OUT_OF_SAMPLE_PROFIT_FACTOR_BELOW_1_10")
        if om["max_drawdown_pct"] > max_drawdown_pct:
            reasons.append("OUT_OF_SAMPLE_DRAWDOWN_LIMIT_BREACHED")
        if not wf_pass:
            reasons.append("WALK_FORWARD_STABILITY_GATE_FAILED")
        eligible = not reasons
        score = (om["net_return_pct"] - 0.75 * om["max_drawdown_pct"] + min(om["profit_factor"], 3.0) * 0.5) if test.get("ready") else -999
        results.append({
            "spec": asdict(spec), "train": train.get("metrics"), "out_of_sample": test.get("metrics"),
            "walk_forward": wf_results, "walk_forward_pass": wf_pass,
            "score": round(score, 4), "paper_trial_eligible": bool(eligible),
            "reasons": reasons,
        })
    results.sort(key=lambda x: (x["paper_trial_eligible"], x["score"]), reverse=True)
    return {
        "success": True, "state": "PAPER_CANDIDATES_READY", "bars": n, "split_index": split,
        "candidates": results, "recommended": next((x for x in results if x["paper_trial_eligible"]), None),
        "governance": {
            "chronological_holdout": True, "costs_included": True, "walk_forward_required_before_paper": True, "walk_forward_folds": 2,
            "minimum_out_of_sample_trades": 3, "automatic_code_rewrite": False,
            "automatic_live_execution": False, "live_execution": False, "paper_only": True,
        },
        "warning": "Historical simulation is not a forecast. Verify data quality, exchange fees, taxes, slippage, expiry behavior and out-of-sample stability before paper trial.",
    }
