from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from typing import Any, Callable
import urllib.parse
import urllib.request


YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

INTERVALS = {
    "1m": ("1m", "7d"),
    "3m": ("5m", "60d"),
    "5m": ("5m", "60d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "1h": ("60m", "2y"),
    "2h": ("60m", "2y"),
    "4h": ("60m", "2y"),
    "1d": ("1d", "5y"),
}


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fetch_json(url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JARVIS-Quant/5.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read(5_000_000).decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Global market-data provider returned an invalid response.")
    return value


def _downsample(candles: list[dict[str, Any]], factor: int) -> list[dict[str, Any]]:
    if factor <= 1:
        return candles
    result: list[dict[str, Any]] = []
    for start in range(0, len(candles), factor):
        group = candles[start : start + factor]
        if len(group) < factor:
            continue
        result.append(
            {
                "time": group[0]["time"],
                "timestamp": group[0]["time"],
                "open": group[0]["open"],
                "high": max(row["high"] for row in group),
                "low": min(row["low"] for row in group),
                "close": group[-1]["close"],
                "volume": sum(row.get("volume", 0.0) for row in group),
            }
        )
    return result


def global_equity_candles(
    provider_symbol: str,
    timeframe: str,
    bars: int,
    *,
    loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    symbol = str(provider_symbol or "").strip().upper()
    if not symbol:
        raise ValueError("A global equity ticker is required.")
    if timeframe not in INTERVALS:
        raise ValueError(f"Unsupported global equity timeframe: {timeframe}")
    interval, range_value = INTERVALS[timeframe]
    query = urllib.parse.urlencode(
        {
            "interval": interval,
            "range": range_value,
            "includePrePost": "false",
            "events": "div,splits",
        }
    )
    url = f"{YAHOO_CHART_BASE}/{urllib.parse.quote(symbol, safe='.^=-')}?{query}"
    try:
        payload = (loader or _fetch_json)(url)
        chart = payload.get("chart") if isinstance(payload, dict) else None
        error = chart.get("error") if isinstance(chart, dict) else None
        if error:
            raise RuntimeError(str(error.get("description") or error.get("code") or error))
        results = chart.get("result") if isinstance(chart, dict) else None
        result = results[0] if isinstance(results, list) and results else None
        if not isinstance(result, dict):
            raise RuntimeError("No global equity chart was returned for this ticker.")
        timestamps = list(result.get("timestamp") or [])
        indicators = result.get("indicators") or {}
        quotes = indicators.get("quote") if isinstance(indicators, dict) else None
        quote = quotes[0] if isinstance(quotes, list) and quotes else {}
        candles: list[dict[str, Any]] = []
        for index, raw_time in enumerate(timestamps):
            values = {
                key: _safe_float((quote.get(key) or [])[index])
                if index < len(quote.get(key) or [])
                else None
                for key in ("open", "high", "low", "close", "volume")
            }
            if any(values[key] is None for key in ("open", "high", "low", "close")):
                continue
            timestamp = int(raw_time)
            candles.append(
                {
                    "time": timestamp,
                    "timestamp": timestamp,
                    "open": values["open"],
                    "high": values["high"],
                    "low": values["low"],
                    "close": values["close"],
                    "volume": values["volume"] or 0.0,
                }
            )
        if timeframe == "2h":
            candles = _downsample(candles, 2)
        elif timeframe == "4h":
            candles = _downsample(candles, 4)
        candles = candles[-max(20, min(int(bars), 7500)) :]
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        return {
            "success": bool(candles),
            "source": "YAHOO_PUBLIC_UNOFFICIAL",
            "data_quality": "PUBLIC_DELAYED_UNOFFICIAL",
            "provider_symbol": symbol,
            "timeframe": timeframe,
            "bars": len(candles),
            "candles": candles,
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "timezone": meta.get("exchangeTimezoneName"),
            "regular_market_price": _safe_float(meta.get("regularMarketPrice")),
            "message": (
                "Global equity candles loaded from an unofficial public Yahoo chart feed. "
                "Data may be delayed and is research-only."
                if candles
                else "The public global equity feed returned no candles."
            ),
            "received_at": datetime.now(timezone.utc).isoformat(),
            "paper_only": True,
            "auto_execution_eligible": False,
            "live_execution": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "source": "YAHOO_PUBLIC_UNOFFICIAL",
            "data_quality": "UNAVAILABLE",
            "provider_symbol": symbol,
            "timeframe": timeframe,
            "bars": 0,
            "candles": [],
            "message": str(exc).replace("\r", " ").replace("\n", " ")[:500],
            "paper_only": True,
            "auto_execution_eligible": False,
            "live_execution": False,
        }


def global_equity_quote(provider_symbol: str) -> dict[str, Any]:
    payload = global_equity_candles(provider_symbol, "1m", 5)
    candles = payload.get("candles") or []
    if not payload.get("success") or not candles:
        return {**payload, "snapshot": None}
    last = candles[-1]
    previous = candles[-2]["close"] if len(candles) > 1 else last["close"]
    change = float(last["close"]) - float(previous)
    percent = (change / float(previous) * 100.0) if previous else 0.0
    return {
        **payload,
        "snapshot": {
            "ltp": last["close"],
            "change": change,
            "change_percent": percent,
            "volume": last.get("volume", 0.0),
            "exchange_timestamp": last["time"],
            "received_at": payload.get("received_at"),
        },
    }

