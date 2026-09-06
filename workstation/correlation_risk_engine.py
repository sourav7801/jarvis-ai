"""Deterministic rolling-return correlation intelligence for JARVIS V7.

This module produces research/risk evidence only.  It does not change portfolio
limits or place orders.  Callers must pass verified completed-bar price series.
"""

from __future__ import annotations

import math
from statistics import fmean
from typing import Any, Mapping, Sequence


def _prices(values: Sequence[Any]) -> list[float]:
    output: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            output.append(number)
    return output


def returns(values: Sequence[Any], *, lookback: int = 120) -> list[float]:
    prices = _prices(values)
    if len(prices) < 3:
        return []
    rows = [(current / previous) - 1.0 for previous, current in zip(prices[:-1], prices[1:]) if previous > 0]
    return rows[-max(5, min(int(lookback), 1000)):]


def correlation(left: Sequence[Any], right: Sequence[Any]) -> float | None:
    a = [float(value) for value in left]
    b = [float(value) for value in right]
    size = min(len(a), len(b))
    if size < 8:
        return None
    a = a[-size:]
    b = b[-size:]
    mean_a = fmean(a)
    mean_b = fmean(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    denom_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    denom_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    if denom_a <= 0 or denom_b <= 0:
        return None
    value = numerator / (denom_a * denom_b)
    return max(-1.0, min(1.0, value))


def correlation_snapshot(
    price_series: Mapping[str, Sequence[Any]],
    *,
    lookback: int = 120,
    cluster_threshold: float = 0.75,
) -> dict[str, Any]:
    threshold = max(0.50, min(abs(float(cluster_threshold)), 0.99))
    prepared = {
        str(symbol).upper(): returns(values, lookback=lookback)
        for symbol, values in price_series.items()
    }
    prepared = {symbol: values for symbol, values in prepared.items() if len(values) >= 8}
    symbols = sorted(prepared)
    matrix: dict[str, dict[str, float | None]] = {symbol: {} for symbol in symbols}
    pairs: list[dict[str, Any]] = []
    for index, left in enumerate(symbols):
        for right in symbols[index:]:
            value = 1.0 if left == right else correlation(prepared[left], prepared[right])
            matrix[left][right] = value
            matrix[right][left] = value
            if left != right and value is not None:
                pairs.append({"left": left, "right": right, "correlation": value, "absolute": abs(value)})
    pairs.sort(key=lambda row: (-float(row["absolute"]), row["left"], row["right"]))

    # Connected components of high absolute correlation form transparent risk clusters.
    adjacency: dict[str, set[str]] = {symbol: set() for symbol in symbols}
    for row in pairs:
        if float(row["absolute"]) >= threshold:
            adjacency[row["left"]].add(row["right"])
            adjacency[row["right"]].add(row["left"])
    clusters: list[list[str]] = []
    seen: set[str] = set()
    for symbol in symbols:
        if symbol in seen:
            continue
        stack = [symbol]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - seen))
        if len(component) > 1:
            clusters.append(sorted(component))

    return {
        "success": True,
        "version": "7.0",
        "symbols": symbols,
        "lookback_returns": max((len(values) for values in prepared.values()), default=0),
        "cluster_threshold": threshold,
        "matrix": matrix,
        "strongest_pairs": pairs[:30],
        "clusters": clusters,
        "portfolio_limit_mutated": False,
        "research_only": True,
        "paper_only": True,
        "live_execution": False,
    }


def from_candles(
    candles_by_symbol: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    lookback: int = 120,
    cluster_threshold: float = 0.75,
) -> dict[str, Any]:
    prices: dict[str, list[float]] = {}
    rejected: list[str] = []
    for symbol, candles in candles_by_symbol.items():
        closes: list[float] = []
        verified = True
        for row in candles:
            if row.get("verified") is False or row.get("stale") is True:
                verified = False
                break
            try:
                closes.append(float(row["close"]))
            except (KeyError, TypeError, ValueError):
                continue
        if not verified:
            rejected.append(str(symbol).upper())
            continue
        prices[str(symbol).upper()] = closes
    result = correlation_snapshot(prices, lookback=lookback, cluster_threshold=cluster_threshold)
    result["rejected_unverified_or_stale"] = sorted(rejected)
    return result


__all__ = ["correlation", "correlation_snapshot", "from_candles", "returns"]
