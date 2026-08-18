
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .analysis_engine import analyze
from .data_bus import DataBus


def build_context(
    data: DataBus,
    symbol: str,
    context_bars: int = 500,
    trigger_bars: int = 1000,
) -> dict[str, Any]:
    context = data.get_history(symbol, "15m", context_bars)
    trigger = data.get_history(symbol, "5m", trigger_bars)

    result = {
        "symbol": symbol,
        "context": {
            "timeframe": "15m",
            "success": bool(context.get("success")),
            "source": context.get("source"),
            "quality": context.get("data_quality"),
        },
        "trigger": {
            "timeframe": "5m",
            "success": bool(trigger.get("success")),
            "source": trigger.get("source"),
            "quality": trigger.get("data_quality"),
        },
        "context_regime": None,
        "trigger_regime": None,
        "tradeable": False,
        "reason": "",
    }

    if not context.get("success") or not trigger.get("success"):
        result["reason"] = "15m context or 5m trigger data unavailable."
        return result

    context_regime = analyze(symbol, context["data"])
    trigger_regime = analyze(symbol, trigger["data"])

    result["context_regime"] = asdict(context_regime)
    result["trigger_regime"] = asdict(trigger_regime)

    aligned_bull = (
        context_regime.direction == "BULLISH"
        and trigger_regime.direction == "BULLISH"
    )
    aligned_bear = (
        context_regime.direction == "BEARISH"
        and trigger_regime.direction == "BEARISH"
    )

    if aligned_bull or aligned_bear:
        result["tradeable"] = True
        result["reason"] = "15m context and 5m trigger are directionally aligned."
    else:
        result["reason"] = "15m context and 5m trigger are not aligned."

    return result
