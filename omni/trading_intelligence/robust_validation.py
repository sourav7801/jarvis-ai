"""Deterministic robustness gates for paper/research strategy candidates.

The validator consumes historical research outputs only.  It does not deploy a
strategy, rewrite production code, or enable broker execution.
"""

from __future__ import annotations

import math
import random
from statistics import fmean, median, pstdev
from typing import Any, Iterable


def _finite(values: Iterable[Any]) -> list[float]:
    output: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            output.append(number)
    return output


def _profit_factor(values: list[float]) -> float:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses > 0:
        return gains / losses
    return 999.0 if gains > 0 else 0.0


def _max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def trade_metrics(values: Iterable[Any]) -> dict[str, Any]:
    rows = _finite(values)
    wins = [value for value in rows if value > 0]
    losses = [value for value in rows if value < 0]
    mean = fmean(rows) if rows else 0.0
    deviation = pstdev(rows) if len(rows) > 1 else 0.0
    downside = [min(value, 0.0) for value in rows]
    downside_deviation = math.sqrt(fmean([value * value for value in downside])) if downside else 0.0
    return {
        "trades": len(rows),
        "expectancy_r": mean,
        "median_r": median(rows) if rows else 0.0,
        "net_r": sum(rows),
        "win_rate": (len(wins) / len(rows)) if rows else 0.0,
        "payoff_ratio": ((fmean(wins) / abs(fmean(losses))) if wins and losses else None),
        "profit_factor": _profit_factor(rows),
        "max_drawdown_r": _max_drawdown(rows),
        "sharpe_like": ((mean / deviation) * math.sqrt(len(rows))) if deviation > 0 else 0.0,
        "sortino_like": ((mean / downside_deviation) * math.sqrt(len(rows))) if downside_deviation > 0 else 0.0,
        "worst_trade_r": min(rows) if rows else 0.0,
        "best_trade_r": max(rows) if rows else 0.0,
    }


def out_of_sample_split(values: Iterable[Any], *, train_fraction: float = 0.70) -> dict[str, Any]:
    rows = _finite(values)
    if len(rows) < 12:
        return {"passed": False, "reason": "INSUFFICIENT_TRADES", "train": trade_metrics([]), "oos": trade_metrics([])}
    fraction = max(0.50, min(float(train_fraction), 0.85))
    split = max(1, min(len(rows) - 1, int(len(rows) * fraction)))
    train = trade_metrics(rows[:split])
    oos = trade_metrics(rows[split:])
    baseline = abs(float(train["expectancy_r"]))
    degradation = None
    if baseline > 1e-9:
        degradation = (float(train["expectancy_r"]) - float(oos["expectancy_r"])) / baseline
    passed = bool(
        oos["trades"] >= 4
        and float(oos["expectancy_r"]) > 0
        and float(oos["profit_factor"]) > 1.0
        and (degradation is None or degradation <= 0.75)
    )
    return {
        "passed": passed,
        "split_index": split,
        "train": train,
        "oos": oos,
        "expectancy_degradation": degradation,
    }


def bootstrap_distribution(
    values: Iterable[Any],
    *,
    samples: int = 400,
    seed: int = 1707,
) -> dict[str, Any]:
    rows = _finite(values)
    if len(rows) < 8:
        return {"passed": False, "reason": "INSUFFICIENT_TRADES", "samples": 0}
    count = max(100, min(int(samples), 2000))
    rng = random.Random(int(seed))
    means: list[float] = []
    drawdowns: list[float] = []
    net_results: list[float] = []
    for _ in range(count):
        sample = [rows[rng.randrange(len(rows))] for _index in range(len(rows))]
        means.append(fmean(sample))
        drawdowns.append(_max_drawdown(sample))
        net_results.append(sum(sample))
    means.sort()
    drawdowns.sort()
    net_results.sort()
    def percentile(values_: list[float], fraction: float) -> float:
        index = min(len(values_) - 1, max(0, int(round((len(values_) - 1) * fraction))))
        return float(values_[index])
    positive_net_rate = sum(1 for value in net_results if value > 0) / len(net_results)
    p05_expectancy = percentile(means, 0.05)
    p95_drawdown = percentile(drawdowns, 0.95)
    return {
        "passed": bool(positive_net_rate >= 0.70 and p05_expectancy > -0.05),
        "samples": count,
        "positive_net_rate": positive_net_rate,
        "expectancy_r_p05": p05_expectancy,
        "expectancy_r_median": percentile(means, 0.50),
        "max_drawdown_r_p95": p95_drawdown,
        "seed": int(seed),
    }


def cost_sensitivity(
    values: Iterable[Any],
    *,
    base_fee_bps: float = 2.0,
    base_slippage_bps: float = 1.0,
) -> dict[str, Any]:
    """Stress R outcomes using conservative normalized cost penalties.

    Research logs often express outcomes in R, not currency.  The stress model
    therefore applies explicit normalized R penalties rather than pretending to
    know venue fees that were not supplied.
    """

    rows = _finite(values)
    if not rows:
        return {"passed": False, "reason": "NO_TRADES", "scenarios": []}
    scenarios: list[dict[str, Any]] = []
    for multiplier in (1.0, 1.5, 2.0, 3.0):
        total_bps = (max(0.0, float(base_fee_bps)) + max(0.0, float(base_slippage_bps))) * multiplier
        penalty_r = min(0.35, total_bps / 100.0)
        stressed = [value - penalty_r for value in rows]
        metrics = trade_metrics(stressed)
        scenarios.append(
            {
                "cost_multiplier": multiplier,
                "assumed_total_bps": total_bps,
                "normalized_penalty_r": penalty_r,
                "expectancy_r": metrics["expectancy_r"],
                "profit_factor": metrics["profit_factor"],
                "max_drawdown_r": metrics["max_drawdown_r"],
            }
        )
    hardest = scenarios[-1]
    return {
        "passed": bool(float(hardest["expectancy_r"]) > 0 and float(hardest["profit_factor"]) > 1.0),
        "scenarios": scenarios,
        "note": "Normalized research stress only; exact venue costs must come from authoritative configuration.",
    }


def validate_research_result(
    backtest: dict[str, Any],
    walk_forward: dict[str, Any] | None = None,
    *,
    seed: int = 1707,
) -> dict[str, Any]:
    trades = list(backtest.get("trade_log") or [])
    r_values = _finite(row.get("r") for row in trades if isinstance(row, dict))
    metrics = trade_metrics(r_values)
    oos = out_of_sample_split(r_values)
    bootstrap = bootstrap_distribution(r_values, seed=seed)
    costs = cost_sensitivity(
        r_values,
        base_fee_bps=float(backtest.get("fee_bps") or 0.0),
        base_slippage_bps=float(backtest.get("slippage_bps") or 0.0),
    )
    walk = dict(walk_forward or {})
    minimum_sample = int(metrics["trades"]) >= 20
    positive = float(metrics["expectancy_r"]) > 0.05 and float(metrics["profit_factor"]) >= 1.15
    drawdown_ok = float(metrics["max_drawdown_r"]) <= 8.0
    walk_ok = bool(walk.get("passed")) if walk else False
    checks = {
        "minimum_sample": minimum_sample,
        "positive_expectancy_and_pf": positive,
        "drawdown": drawdown_ok,
        "walk_forward": walk_ok,
        "out_of_sample": bool(oos.get("passed")),
        "bootstrap": bool(bootstrap.get("passed")),
        "cost_sensitivity": bool(costs.get("passed")),
    }
    passed = all(checks.values())
    return {
        "success": True,
        "passed": passed,
        "status": "PAPER_CHALLENGER_ELIGIBLE" if passed else "RESEARCH_ONLY",
        "checks": checks,
        "metrics": metrics,
        "out_of_sample": oos,
        "bootstrap": bootstrap,
        "cost_sensitivity": costs,
        "governance": {
            "automatic_production_promotion": False,
            "automatic_live_promotion": False,
            "paper_challenger_only": True,
            "requires_explicit_governed_promotion": True,
        },
        "research_only": True,
        "live_execution": False,
    }


__all__ = [
    "bootstrap_distribution",
    "cost_sensitivity",
    "out_of_sample_split",
    "trade_metrics",
    "validate_research_result",
]
