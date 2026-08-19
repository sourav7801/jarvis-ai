from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
import re
import urllib.parse
import urllib.request
from typing import Any


DERIBIT_HTTP = "https://www.deribit.com/api/v2"
DERIBIT_WS = "wss://www.deribit.com/ws/api/v2"

_DERIBIT_RESOLUTION = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "10m": "10",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "3h": "180",
    "6h": "360",
    "12h": "720",
    "1d": "1D",
}

_TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "10m": 600,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "3h": 10800,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
}

_SAFE_INSTRUMENT = re.compile(r"^[A-Za-z0-9:._-]{3,120}$")


def _safe_message(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ")[:700]


def _instrument(value: str) -> str:
    instrument = str(value or "").strip()
    if not _SAFE_INSTRUMENT.fullmatch(instrument):
        raise ValueError("Invalid option instrument identifier.")
    return instrument


def _timeframe(value: str) -> str:
    key = str(value or "5m").strip().lower()
    aliases = {
        "1": "1m",
        "3": "3m",
        "5": "5m",
        "10": "10m",
        "15": "15m",
        "30": "30m",
        "60": "1h",
        "120": "2h",
        "180": "3h",
        "360": "6h",
        "720": "12h",
        "d": "1d",
        "day": "1d",
        "daily": "1d",
    }
    resolved = aliases.get(key, key)
    if resolved not in _TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported option chart timeframe: {value}")
    return resolved


def _deribit_json(path: str, params: dict[str, Any], timeout: float = 8.0) -> Any:
    request = urllib.request.Request(
        DERIBIT_HTTP + path + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "JARVIS-Quant-Option-Chart/3.3"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Deribit option-chart response was not a JSON object.")
    if payload.get("error"):
        raise RuntimeError(str(payload.get("error"))[:500])
    return payload.get("result")


def _frame_candles(frame: Any) -> list[dict[str, Any]]:
    if frame is None or not hasattr(frame, "reset_index"):
        return []
    table = frame.reset_index()
    columns = {str(column).strip().lower(): column for column in table.columns}
    time_column = None
    for candidate in ("timestamp", "datetime", "date", "time", "index"):
        if candidate in columns:
            time_column = columns[candidate]
            break
    if time_column is None:
        return []

    required = {name: columns.get(name) for name in ("open", "high", "low", "close")}
    if any(value is None for value in required.values()):
        return []
    volume_column = columns.get("volume")

    candles: list[dict[str, Any]] = []
    for _, row in table.iterrows():
        try:
            stamp = row[time_column]
            if hasattr(stamp, "timestamp"):
                timestamp = int(stamp.timestamp())
            else:
                import pandas as pd

                timestamp = int(pd.Timestamp(stamp).timestamp())
            candle = {
                "time": timestamp,
                "timestamp": timestamp,
                "open": float(row[required["open"]]),
                "high": float(row[required["high"]]),
                "low": float(row[required["low"]]),
                "close": float(row[required["close"]]),
                "volume": float(row[volume_column]) if volume_column is not None else 0.0,
            }
        except (TypeError, ValueError, OverflowError):
            continue
        if all(math.isfinite(candle[key]) for key in ("open", "high", "low", "close")):
            candles.append(candle)
    return candles


def _deribit_candles(instrument: str, timeframe: str, bars: int) -> dict[str, Any]:
    resolution = _DERIBIT_RESOLUTION.get(timeframe)
    if resolution is None:
        raise ValueError(f"Deribit does not expose {timeframe} option candles directly.")
    bounded = max(20, min(int(bars), 3000))
    end = datetime.now(timezone.utc)
    seconds = _TIMEFRAME_SECONDS[timeframe]
    start = end - timedelta(seconds=max(seconds * bounded * 2, 86400))
    result = _deribit_json(
        "/public/get_tradingview_chart_data",
        {
            "instrument_name": instrument,
            "start_timestamp": int(start.timestamp() * 1000),
            "end_timestamp": int(end.timestamp() * 1000),
            "resolution": resolution,
        },
    )
    result = dict(result or {})
    if str(result.get("status") or "").lower() != "ok":
        return {
            "success": False,
            "source": "DERIBIT_PUBLIC",
            "provider_symbol": instrument,
            "timeframe": timeframe,
            "bars": 0,
            "candles": [],
            "message": "Deribit returned no option candle data.",
            "paper_only": True,
            "live_execution": False,
        }

    arrays = [
        list(result.get("ticks") or []),
        list(result.get("open") or []),
        list(result.get("high") or []),
        list(result.get("low") or []),
        list(result.get("close") or []),
        list(result.get("volume") or []),
    ]
    count = min(len(values) for values in arrays[:5]) if arrays[:5] else 0
    candles: list[dict[str, Any]] = []
    for index in range(count):
        try:
            candle = {
                "time": int(float(arrays[0][index]) / 1000.0),
                "timestamp": int(float(arrays[0][index]) / 1000.0),
                "open": float(arrays[1][index]),
                "high": float(arrays[2][index]),
                "low": float(arrays[3][index]),
                "close": float(arrays[4][index]),
                "volume": float(arrays[5][index]) if index < len(arrays[5]) else 0.0,
            }
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(candle[key]) for key in ("open", "high", "low", "close")):
            candles.append(candle)
    candles = candles[-bounded:]
    return {
        "success": bool(candles),
        "source": "DERIBIT_PUBLIC",
        "data_quality": "PUBLIC_EXCHANGE_OPTION_HISTORICAL",
        "provider_symbol": instrument,
        "timeframe": timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": "Public option candles loaded from Deribit." if candles else "No valid Deribit option candles were returned.",
        "paper_only": True,
        "live_execution": False,
    }


def _fyers_candles(instrument: str, timeframe: str, bars: int) -> dict[str, Any]:
    from workstation.fyers_isolated_history_bridge import get_intraday_data_isolated_frame

    result = get_intraday_data_isolated_frame(
        instrument,
        market="india",
        timeframe=timeframe,
        bars=max(20, min(int(bars), 2000)),
        timeout=30,
    )
    payload = dict(result) if isinstance(result, dict) else {}
    candles = _frame_candles(payload.get("data")) if payload.get("success") else []
    return {
        "success": bool(payload.get("success") and candles),
        "source": "FYERS_READ_ONLY",
        "data_quality": payload.get("data_quality") or ("BROKER_OPTION_HISTORICAL" if candles else "UNAVAILABLE"),
        "provider_symbol": payload.get("provider_symbol") or instrument,
        "timeframe": timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": payload.get("message") or ("Verified FYERS option candles loaded." if candles else "FYERS option candles unavailable."),
        "paper_only": True,
        "live_execution": False,
    }


def option_candles(provider: str, instrument: str, timeframe: str = "5m", bars: int = 500) -> dict[str, Any]:
    resolved_provider = str(provider or "").strip().upper()
    resolved_instrument = _instrument(instrument)
    resolved_timeframe = _timeframe(timeframe)
    if resolved_provider == "DERIBIT_PUBLIC":
        return _deribit_candles(resolved_instrument, resolved_timeframe, bars)
    if resolved_provider in {"FYERS", "FYERS_READ_ONLY"}:
        return _fyers_candles(resolved_instrument, resolved_timeframe, bars)
    raise ValueError(f"Unsupported option-chart provider: {provider}")


def option_live(provider: str, instrument: str) -> dict[str, Any]:
    resolved_provider = str(provider or "").strip().upper()
    resolved_instrument = _instrument(instrument)
    if resolved_provider == "DERIBIT_PUBLIC":
        ticker = dict(_deribit_json("/public/ticker", {"instrument_name": resolved_instrument}) or {})
        price = ticker.get("last_price")
        if price is None:
            price = ticker.get("mark_price")
        return {
            "success": price is not None,
            "source": "DERIBIT_PUBLIC",
            "provider_symbol": resolved_instrument,
            "snapshot": {
                "ltp": price,
                "mark_price": ticker.get("mark_price"),
                "bid": ticker.get("best_bid_price"),
                "ask": ticker.get("best_ask_price"),
                "mark_iv": ticker.get("mark_iv"),
                "open_interest": ticker.get("open_interest"),
                "underlying_price": ticker.get("underlying_price") or ticker.get("index_price"),
                "greeks": ticker.get("greeks") or {},
                "exchange_timestamp": int(float(ticker.get("timestamp") or 0) / 1000.0) if ticker.get("timestamp") else None,
            },
            "paper_only": True,
            "live_execution": False,
        }
    return {
        "success": False,
        "source": resolved_provider or "FYERS_READ_ONLY",
        "provider_symbol": resolved_instrument,
        "snapshot": None,
        "message": "Dynamic Indian-option live subscription is not enabled yet; historical option candles remain verified through FYERS.",
        "paper_only": True,
        "live_execution": False,
    }


def attach_chart_directive(command: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    result = deepcopy(payload)
    text = str(command or "").lower()
    if not re.search(r"\b(chart|graph|plot)\b", text):
        return result

    action = str(result.get("action") or "")
    chart: dict[str, Any] | None = None

    if action == "option_analysis":
        request = result.get("request") if isinstance(result.get("request"), dict) else {}
        option_type = str(request.get("option_type") or "").lower()
        candidates = [row for row in result.get("candidates") or [] if isinstance(row, dict)]
        if option_type:
            candidates = [row for row in candidates if str(row.get("option_type") or "").lower() == option_type]
        if candidates:
            selected = candidates[0]
            chart = {
                "kind": "OPTION",
                "provider": "DERIBIT_PUBLIC",
                "instrument_name": selected.get("instrument_name"),
                "label": selected.get("instrument_name"),
                "underlying": request.get("underlying"),
                "strike": selected.get("strike"),
                "option_type": str(selected.get("option_type") or "").upper(),
                "expiry": selected.get("expiry"),
                "websocket_url": DERIBIT_WS,
                "realtime_channel": f"ticker.{selected.get('instrument_name')}.100ms",
            }

    elif action == "india_option_analysis":
        request = result.get("request") if isinstance(result.get("request"), dict) else {}
        contract = result.get("contract") if isinstance(result.get("contract"), dict) else None
        if contract and contract.get("symbol"):
            chart = {
                "kind": "OPTION",
                "provider": "FYERS_READ_ONLY",
                "instrument_name": contract.get("symbol"),
                "label": contract.get("symbol"),
                "underlying": request.get("underlying"),
                "strike": contract.get("strike"),
                "option_type": contract.get("option_type"),
                "expiry": (result.get("paper_intent") or {}).get("expiry") if isinstance(result.get("paper_intent"), dict) else None,
                "realtime_channel": None,
            }

    if chart and chart.get("instrument_name"):
        result["chart"] = chart
        speech = str(result.get("speech") or "").strip()
        if "chart" not in speech.lower():
            result["speech"] = (speech + " Opening the verified option chart.").strip()
    return result
