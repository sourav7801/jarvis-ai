"""Read-only FYERS API v3 market-data adapter.

The public result shape matches JARVIS' existing broker adapter so the trading
core can switch providers without changing strategy code.  No order endpoints
are imported or exposed.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import math
import os
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from agents.fyers_auth_manager import create_client, is_configured


INDIA_TZ = ZoneInfo("Asia/Kolkata")

SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}

RESOLUTIONS = {
    "1m": "1",
    "2m": "2",
    "3m": "3",
    "5m": "5",
    "10m": "10",
    "15m": "15",
    "20m": "20",
    "30m": "30",
    "1h": "60",
    "60m": "60",
    "2h": "120",
    "4h": "240",
    "1d": "D",
    "d": "D",
    "1wk": "1W",
    "1w": "1W",
    "1mo": "1M",
}


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if not value:
        raise ValueError("Symbol is required.")
    if ":" in value:
        return value
    mapped = SYMBOLS.get(value)
    if mapped:
        return mapped
    raise ValueError(
        f"Unknown FYERS symbol alias '{symbol}'. Use a full symbol such as "
        "NSE:SBIN-EQ, or set one of NIFTY, BANKNIFTY, SENSEX."
    )


def resolution_for(timeframe: str) -> str:
    key = str(timeframe or "").strip().lower()
    try:
        return RESOLUTIONS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported FYERS timeframe: {timeframe}") from exc


def _calendar_days_for_bars(bars: int, resolution: str) -> int:
    if resolution.isdigit():
        minutes = max(int(resolution), 1)
        bars_per_session = max(1, 375 // minutes)
        trading_days = math.ceil(bars / bars_per_session) + 5
        return max(10, math.ceil(trading_days * 7 / 5) + 5)
    if resolution in {"D", "1D"}:
        return max(30, math.ceil(bars * 7 / 5) + 15)
    if resolution == "1W":
        return max(90, bars * 7 + 30)
    return max(365, bars * 31 + 31)


def _windows(start: date, end: date, max_days: int) -> Iterable[tuple[date, date]]:
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=max_days - 1), end)
        yield cursor, window_end
        cursor = window_end + timedelta(days=1)


def _response_error(response: Any) -> str:
    if isinstance(response, dict):
        message = str(
            response.get("message")
            or response.get("msg")
            or response.get("code")
            or response.get("s")
            or "Unknown FYERS response"
        )
        if message.strip().lower() == "bad request":
            return (
                "FYERS rejected the request. The daily login session may have "
                "expired; run the FYERS login command and try again."
            )
        return message
    return f"Invalid FYERS response: {type(response).__name__}"


def candles_to_frame(rows: list[list[Any]]) -> pd.DataFrame:
    valid = [row[:6] for row in rows if isinstance(row, (list, tuple)) and len(row) >= 6]
    if not valid:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    frame = pd.DataFrame(
        valid,
        columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"],
    )
    frame["Timestamp"] = pd.to_datetime(
        frame["Timestamp"], unit="s", utc=True, errors="coerce"
    ).dt.tz_convert(INDIA_TZ)
    for column in ("Open", "High", "Low", "Close", "Volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(
        subset=["Timestamp", "Open", "High", "Low", "Close"]
    )
    return (
        frame.drop_duplicates(subset=["Timestamp"], keep="last")
        .sort_values("Timestamp")
        .set_index("Timestamp")
    )


def get_intraday_data(
    symbol: str,
    market: str = "india",
    timeframe: str = "5m",
    bars: int = 500,
    *,
    client: Any = None,
) -> dict[str, Any]:
    requested_symbol = str(symbol or "").strip().upper()
    if str(market or "").strip().lower() not in {"india", "indian", "nse", "bse"}:
        return {
            "success": False,
            "source": "FYERS",
            "message": "The FYERS adapter currently supports Indian markets only.",
        }
    if bars <= 0:
        return {
            "success": False,
            "source": "FYERS",
            "message": "bars must be greater than zero.",
        }

    try:
        provider_symbol = normalize_symbol(symbol)
        resolution = resolution_for(timeframe)
    except ValueError as exc:
        return {
            "success": False,
            "source": "FYERS",
            "message": str(exc),
            "bars": 0,
            "data": None,
        }

    if client is None and not is_configured():
        return {
            "success": False,
            "source": "FYERS",
            "message": (
                "FYERS is not configured. Set FYERS_APP_ID and run "
                "python -m agents.fyers_auth_manager login."
            ),
            "bars": 0,
            "data": None,
        }

    try:
        fyers = client or create_client()
        end = datetime.now(INDIA_TZ).date()
        start = end - timedelta(days=_calendar_days_for_bars(bars, resolution))
        max_days = 100 if resolution.isdigit() else 366
        rows: list[list[Any]] = []
        errors: list[str] = []

        for range_from, range_to in _windows(start, end, max_days):
            response = fyers.history(
                data={
                    "symbol": provider_symbol,
                    "resolution": resolution,
                    "date_format": "1",
                    "range_from": range_from.isoformat(),
                    "range_to": range_to.isoformat(),
                    "cont_flag": "1",
                }
            )
            if isinstance(response, dict) and response.get("s") == "ok":
                rows.extend(response.get("candles") or [])
            elif isinstance(response, dict) and response.get("s") == "no_data":
                continue
            else:
                errors.append(_response_error(response))

        frame = candles_to_frame(rows).tail(bars)
        if frame.empty:
            return {
                "success": False,
                "source": "FYERS",
                "data_quality": "UNAVAILABLE",
                "symbol": requested_symbol,
                "provider_symbol": provider_symbol,
                "timeframe": timeframe,
                "bars": 0,
                "data": None,
                "message": errors[-1] if errors else "FYERS returned no candles.",
            }

        return {
            "success": True,
            "source": "FYERS",
            "data_quality": "BROKER_HISTORICAL",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": len(frame),
            "data": frame,
            "message": "Historical candles loaded from FYERS API v3.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "success": False,
            "source": "FYERS",
            "data_quality": "UNAVAILABLE",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": 0,
            "data": None,
            "message": str(exc),
        }


def get_quote(symbol: str, *, client: Any = None) -> dict[str, Any]:
    try:
        provider_symbol = normalize_symbol(symbol)
        fyers = client or create_client()
        response = fyers.quotes(data={"symbols": provider_symbol})
        items = response.get("d", []) if isinstance(response, dict) else []
        if not items:
            raise RuntimeError(_response_error(response))
        item = items[0]
        values = item.get("v", {}) if isinstance(item, dict) else {}
        return {
            "success": True,
            "source": "FYERS",
            "symbol": str(symbol).strip().upper(),
            "provider_symbol": provider_symbol,
            "ltp": values.get("lp"),
            "change": values.get("ch"),
            "change_percent": values.get("chp"),
            "open": values.get("open_price"),
            "high": values.get("high_price"),
            "low": values.get("low_price"),
            "previous_close": values.get("prev_close_price"),
            "volume": values.get("volume"),
            "bid": values.get("bid"),
            "ask": values.get("ask"),
            "exchange_timestamp": values.get("tt"),
        }
    except Exception as exc:
        return {
            "success": False,
            "source": "FYERS",
            "symbol": str(symbol or "").strip().upper(),
            "message": str(exc),
        }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Test JARVIS FYERS market data")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--bars", type=int, default=20)
    parser.add_argument("--quote", action="store_true")
    args = parser.parse_args(argv)
    result = (
        get_quote(args.symbol)
        if args.quote
        else get_intraday_data(
            args.symbol, timeframe=args.timeframe, bars=args.bars
        )
    )
    printable = {key: value for key, value in result.items() if key != "data"}
    print(printable)
    if result.get("success") and result.get("data") is not None:
        print(result["data"].tail())
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
