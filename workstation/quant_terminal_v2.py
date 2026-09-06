from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from omni.loopback_http import exclusive_server
from omni.service_health_contract import ServiceHealthClock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC = PROJECT_ROOT / "workstation" / "quant_terminal_v2_static"
HOST = os.getenv("JARVIS_WORKSTATION_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_WORKSTATION_PORT", "8787"))
LIVE_BRIDGE_HOST = os.getenv("JARVIS_FYERS_BRIDGE_HOST", "127.0.0.1")
LIVE_BRIDGE_PORT = int(os.getenv("JARVIS_FYERS_BRIDGE_PORT", "8790"))
LIVE_BRIDGE_URL = f"http://{LIVE_BRIDGE_HOST}:{LIVE_BRIDGE_PORT}"
AUTO_PAPER_START = os.getenv("JARVIS_AUTO_PAPER_START", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

CRYPTO_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
}
INDIA_SYMBOLS = {
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "GOLD",
    "SILVER",
    "NATURALGAS",
}
SUPPORTED_SYMBOLS = tuple(
    ["NIFTY", "BANKNIFTY", "SENSEX", "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"]
    + list(CRYPTO_SYMBOLS)
)
SUPPORTED_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}

# One governed decision horizon is used by the scanner, chart signal and paper
# executor.  A chart's visual timeframe may change, but that must never create
# a second, contradictory trade instruction.
CONSENSUS_TIMEFRAMES = ("5m", "15m", "1h")
SWING_CONSENSUS_TIMEFRAMES = ("1h", "4h", "1d")
CONSENSUS_MIN_SCORE = 68.0
CONSENSUS_MIN_ALIGNMENT = 67
CONSENSUS_MIN_RISK_REWARD = 1.8

_LIVE_BRIDGE_PROCESS: subprocess.Popen | None = None
_QUOTE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_QUOTE_CACHE_LOCK = threading.RLock()
HEALTH = ServiceHealthClock("JARVIS_QUANT_TERMINAL", "5.0")


def _safe_message(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ")[:700]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def normalize_symbol(value: str) -> str:
    raw = str(value or "").strip()
    symbol = raw.upper().replace(" ", "")
    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTY": "NIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "SENSEX": "SENSEX",
        "CRUDE": "CRUDEOIL",
        "CRUDEOIL": "CRUDEOIL",
        "NATGAS": "NATURALGAS",
        "NATURALGAS": "NATURALGAS",
        "GOLD": "GOLD",
        "SILVER": "SILVER",
        "BITCOIN": "BTC",
        "BTC": "BTC",
        "ETHEREUM": "ETH",
        "ETHER": "ETH",
        "ETH": "ETH",
        "SOLANA": "SOL",
        "SOL": "SOL",
    }
    result = aliases.get(symbol, symbol)
    if result in SUPPORTED_SYMBOLS:
        return result
    from workstation.equity_universe import resolve_equity_symbol

    equity = resolve_equity_symbol(raw)
    if equity is not None:
        return equity.symbol
    raise ValueError(
        f"Unsupported Quant Terminal symbol: {value}. For global equities use an explicit "
        "ticker such as NASDAQ:AAPL, NYSE:IBM, or YF:7203.T."
    )


def symbol_metadata(value: str) -> dict[str, Any]:
    canonical = normalize_symbol(value)
    if canonical in CRYPTO_SYMBOLS:
        return {
            "symbol": canonical,
            "label": canonical,
            "kind": "CRYPTO",
            "market": "CRYPTO",
            "provider": "BINANCE_PUBLIC",
            "provider_symbol": CRYPTO_SYMBOLS[canonical],
            "auto_execution_eligible": True,
        }
    if canonical in INDIA_SYMBOLS:
        return {
            "symbol": canonical,
            "label": canonical,
            "kind": "INDIA",
            "market": "INDIA",
            "provider": "FYERS",
            "provider_symbol": canonical,
            "auto_execution_eligible": True,
        }
    from workstation.equity_universe import resolve_equity_symbol

    equity = resolve_equity_symbol(canonical) or resolve_equity_symbol(value)
    if equity is None:
        raise ValueError(f"Equity metadata is unavailable for {value}.")
    return {**equity.to_dict(), "auto_execution_eligible": equity.market == "INDIA"}


def normalize_timeframe(value: str) -> str:
    timeframe = str(value or "5m").strip().lower()
    aliases = {
        "1": "1m",
        "3": "3m",
        "5": "5m",
        "15": "15m",
        "30": "30m",
        "60": "1h",
        "120": "2h",
        "240": "4h",
        "d": "1d",
        "day": "1d",
        "daily": "1d",
    }
    timeframe = aliases.get(timeframe, timeframe)
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {value}")
    return timeframe


def _timestamp_seconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        return int(number)
    try:
        import pandas as pd

        stamp = pd.Timestamp(value)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("Asia/Kolkata")
        return int(stamp.timestamp())
    except Exception:
        return None


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

    def col(name: str):
        return columns.get(name.lower())

    required = {name: col(name) for name in ("open", "high", "low", "close")}
    if any(value is None for value in required.values()):
        return []
    volume_column = col("volume")
    candles = []
    for _, row in table.iterrows():
        timestamp = _timestamp_seconds(row[time_column])
        if timestamp is None:
            continue
        try:
            candle = {
                "time": timestamp,
                "timestamp": timestamp,
                "open": float(row[required["open"]]),
                "high": float(row[required["high"]]),
                "low": float(row[required["low"]]),
                "close": float(row[required["close"]]),
                "volume": float(row[volume_column]) if volume_column is not None else 0.0,
            }
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(candle[key]) for key in ("open", "high", "low", "close")):
            candles.append(candle)
    return candles


def _fyers_candles(
    symbol: str,
    timeframe: str,
    bars: int,
    *,
    provider_symbol: str | None = None,
) -> dict[str, Any]:
    from workstation.fyers_isolated_history_bridge import get_intraday_data_isolated_frame

    result = get_intraday_data_isolated_frame(
        provider_symbol or symbol,
        market="india",
        timeframe=timeframe,
        bars=bars,
        timeout=25,
    )
    payload = dict(result) if isinstance(result, dict) else {}
    candles = _frame_candles(payload.get("data")) if payload.get("success") else []
    return {
        "success": bool(payload.get("success") and candles),
        "source": payload.get("source") or "FYERS",
        "data_quality": payload.get("data_quality") or (
            "BROKER_HISTORICAL" if candles else "UNAVAILABLE"
        ),
        "symbol": symbol,
        "provider_symbol": payload.get("provider_symbol") or provider_symbol or symbol,
        "timeframe": timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": payload.get("message") or (
            "Historical candles loaded from FYERS." if candles else "FYERS candles unavailable."
        ),
        "paper_only": True,
        "live_execution": False,
    }


def _binance_interval(timeframe: str) -> str:
    mapping = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "1d": "1d",
    }
    return mapping[timeframe]


_TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}


def completed_candles(
    candles: list[dict[str, Any]],
    timeframe: str,
    *,
    now_epoch: float | None = None,
) -> list[dict[str, Any]]:
    """Exclude a provider's still-forming final bar from strategy evidence."""

    if not candles:
        return []
    now_value = float(now_epoch if now_epoch is not None else time.time())
    interval_seconds = _TIMEFRAME_SECONDS.get(normalize_timeframe(timeframe))
    result: list[dict[str, Any]] = []
    for row in candles:
        close_time = row.get("close_time")
        if close_time is None and interval_seconds:
            opened = row.get("time", row.get("timestamp"))
            try:
                close_time = float(opened) + interval_seconds
            except (TypeError, ValueError):
                close_time = None
        if close_time is None or float(close_time) <= now_value:
            result.append(row)
    return result


def _binance_json(path: str, params: dict[str, Any]) -> Any:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"https://api.binance.com{path}?{query}",
        headers={"User-Agent": "JARVIS-Quant-Research/2.0"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def _crypto_candles(symbol: str, timeframe: str, bars: int) -> dict[str, Any]:
    provider_symbol = CRYPTO_SYMBOLS[symbol]
    try:
        rows = _binance_json(
            "/api/v3/klines",
            {
                "symbol": provider_symbol,
                "interval": _binance_interval(timeframe),
                "limit": max(1, min(int(bars), 1000)),
            },
        )
        candles = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 6:
                continue
            candles.append(
                {
                    "time": int(int(row[0]) / 1000),
                    "timestamp": int(int(row[0]) / 1000),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "close_time": int(int(row[6]) / 1000) if len(row) > 6 else None,
                }
            )
        return {
            "success": bool(candles),
            "source": "BINANCE_PUBLIC",
            "data_quality": "PUBLIC_EXCHANGE_HISTORICAL",
            "symbol": symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": len(candles),
            "candles": candles,
            "message": "Public crypto candles loaded from Binance." if candles else "No crypto candles returned.",
            "paper_only": True,
            "live_execution": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "source": "BINANCE_PUBLIC",
            "data_quality": "UNAVAILABLE",
            "symbol": symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": 0,
            "candles": [],
            "message": _safe_message(exc),
            "paper_only": True,
            "live_execution": False,
        }


def candles_payload(symbol: str, timeframe: str = "5m", bars: int = 500) -> dict[str, Any]:
    canonical = normalize_symbol(symbol)
    resolved_timeframe = normalize_timeframe(timeframe)
    bounded_bars = max(20, min(int(bars), 7500))
    if canonical in CRYPTO_SYMBOLS:
        return _crypto_candles(canonical, resolved_timeframe, bounded_bars)
    if canonical not in INDIA_SYMBOLS:
        metadata = symbol_metadata(canonical)
        if metadata.get("market") == "GLOBAL":
            from workstation.global_equity_data import global_equity_candles

            payload = global_equity_candles(
                str(metadata["provider_symbol"]), resolved_timeframe, bounded_bars
            )
            payload["symbol"] = canonical
            payload["instrument"] = metadata
            return payload
        payload = _fyers_candles(
            canonical,
            resolved_timeframe,
            bounded_bars,
            provider_symbol=str(metadata["provider_symbol"]),
        )
        payload["instrument"] = metadata
        if payload.get("success") and _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
            _bridge_request(
                "/api/subscribe",
                method="POST",
                timeout=1.5,
                payload={"symbol": metadata["provider_symbol"]},
            )
        return payload
    return _fyers_candles(canonical, resolved_timeframe, bounded_bars)


def _bridge_request(
    path: str,
    method: str = "GET",
    timeout: float = 1.5,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    data = json.dumps(payload or {}).encode("utf-8") if method == "POST" else None
    request = urllib.request.Request(
        LIVE_BRIDGE_URL + path,
        method=method,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
            return value if isinstance(value, dict) else None
    except Exception:
        return None


def _port_open(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.2)
    try:
        return sock.connect_ex((host, int(port))) == 0
    finally:
        sock.close()


def start_live_bridge() -> bool:
    global _LIVE_BRIDGE_PROCESS
    if _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
        return True

    from omni.runtime_paths import fyers_python

    python = fyers_python()
    if not python.exists():
        return False

    flags = 0
    if os.name == "nt":
        flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    try:
        _LIVE_BRIDGE_PROCESS = subprocess.Popen(
            [str(python), "-m", "workstation.fyers_live_bridge_service"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception:
        return False

    deadline = time.time() + 3.0
    while time.time() < deadline:
        if _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
            return True
        time.sleep(0.1)
    return False


def provider_payload() -> dict[str, Any]:
    from agents.fyers_auth_manager import FyersSettings, is_configured

    settings = FyersSettings.from_env()
    configured = bool(is_configured())
    bridge = _bridge_request("/api/status") if _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT) else None
    if bridge and bridge.get("connected") and bridge.get("error"):
        state = "DEGRADED"
    elif bridge and bridge.get("connected"):
        state = "CONNECTED"
    elif bridge and bridge.get("running"):
        state = "CONNECTING"
    elif configured:
        state = "SESSION_UNAVAILABLE"
    else:
        state = "LOGIN_REQUIRED"
    return {
        "provider": "FYERS",
        "state": state,
        "configured": configured,
        "token_saved": bool(settings.token_file.exists()),
        "bridge_available": bool(bridge),
        "bridge": bridge or {
            "running": False,
            "connected": False,
            "error": "FYERS live bridge is not running.",
            "data_only": True,
            "live_orders": False,
        },
        "crypto": {
            "provider": "BINANCE_PUBLIC",
            "symbols": list(CRYPTO_SYMBOLS),
            "credentials_required": False,
        },
        "paper_only": True,
        "live_execution": False,
    }


def provider_health_state(provider: dict[str, Any]) -> tuple[bool, str | None]:
    bridge = provider.get("bridge") if isinstance(provider.get("bridge"), dict) else {}
    ready = str(provider.get("state") or "").upper() == "CONNECTED" and bool(
        bridge.get("connected")
    )
    error = bridge.get("error") or provider.get("message") or provider.get("error")
    return ready, str(error)[:500] if error else None


def live_payload(symbol: str) -> dict[str, Any]:
    canonical = normalize_symbol(symbol)
    if canonical in CRYPTO_SYMBOLS:
        provider_symbol = CRYPTO_SYMBOLS[canonical]
        try:
            ticker = _binance_json("/api/v3/ticker/24hr", {"symbol": provider_symbol})
            return {
                "success": True,
                "source": "BINANCE_PUBLIC",
                "symbol": canonical,
                "provider_symbol": provider_symbol,
                "snapshot": {
                    "ltp": float(ticker["lastPrice"]),
                    "change": float(ticker["priceChange"]),
                    "change_percent": float(ticker["priceChangePercent"]),
                    "volume": float(ticker["volume"]),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                },
                "live_orders": False,
            }
        except Exception as exc:
            return {
                "success": False,
                "source": "BINANCE_PUBLIC",
                "symbol": canonical,
                "snapshot": None,
                "message": _safe_message(exc),
                "live_orders": False,
            }

    metadata = symbol_metadata(canonical)
    if metadata.get("market") == "GLOBAL":
        from workstation.global_equity_data import global_equity_quote

        payload = global_equity_quote(str(metadata["provider_symbol"]))
        payload["symbol"] = canonical
        payload["instrument"] = metadata
        payload["live_orders"] = False
        return payload

    if not _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
        start_live_bridge()
    bridge_symbol = str(metadata.get("provider_symbol") or canonical)
    payload = _bridge_request(
        "/api/snapshot?" + urllib.parse.urlencode({"symbol": bridge_symbol}),
        timeout=1.2,
    )
    bridge_snapshot = dict(payload.get("snapshot") or {}) if payload else {}
    bridge_status = dict(payload.get("status") or {}) if payload else {}
    bridge_received = str(bridge_snapshot.get("received_at") or "").strip()
    bridge_age_seconds: float | None = None
    if bridge_received:
        try:
            parsed_received = datetime.fromisoformat(bridge_received.replace("Z", "+00:00"))
            if parsed_received.tzinfo is None:
                parsed_received = parsed_received.replace(tzinfo=timezone.utc)
            bridge_age_seconds = max(
                0.0,
                (datetime.now(timezone.utc) - parsed_received.astimezone(timezone.utc)).total_seconds(),
            )
        except ValueError:
            bridge_age_seconds = None
    bridge_healthy = bool(
        payload
        and payload.get("success")
        and bridge_snapshot.get("ltp") is not None
        and bridge_status.get("connected")
        and not bridge_status.get("error")
        and bridge_age_seconds is not None
        and bridge_age_seconds <= 30.0
    )
    if bridge_healthy:
        payload["symbol"] = canonical
        payload["instrument"] = metadata
        payload["snapshot_kind"] = "LIVE_STREAM"
        payload["stream_degraded"] = False
        payload["snapshot_age_seconds"] = round(bridge_age_seconds or 0.0, 3)
        payload["live_orders"] = False
        return payload

    # The stream is an optimization, not the only read path. This fallback is
    # used for fixed indices/commodities as well as dynamically selected Indian
    # equities, so a reconnecting socket can never leave the whole watchlist
    # blank after a successful FYERS login.
    now_mono = time.monotonic()
    with _QUOTE_CACHE_LOCK:
        cached = _QUOTE_CACHE.get(canonical)
        if cached and now_mono - cached[0] < 2.0:
            return dict(cached[1])
    try:
        from agents.fyers_data_adapter import get_quote

        quote = get_quote(bridge_symbol)
        if quote.get("success"):
            result = {
                "success": True,
                "source": "FYERS",
                "symbol": canonical,
                "provider_symbol": bridge_symbol,
                "instrument": metadata,
                "snapshot_kind": "REST_QUOTE_FALLBACK",
                "stream_degraded": True,
                "stream_error": bridge_status.get("error") or "LIVE_STREAM_UNAVAILABLE",
                "snapshot": {
                    key: quote.get(key)
                    for key in (
                        "ltp", "change", "change_percent", "open", "high", "low",
                        "previous_close", "volume", "bid", "ask", "exchange_timestamp"
                    )
                },
                "live_orders": False,
            }
            result["snapshot"]["received_at"] = datetime.now(timezone.utc).isoformat()
            with _QUOTE_CACHE_LOCK:
                _QUOTE_CACHE[canonical] = (now_mono, result)
            return result
    except Exception as exc:
        fallback_error = _safe_message(exc)
    else:
        fallback_error = "FYERS quote response contained no verified price."

    # A cached stream price is still useful for display after market close, but
    # it is explicitly labelled stale and cannot masquerade as a live mark.
    if payload and payload.get("success") and bridge_snapshot.get("ltp") is not None:
        payload["symbol"] = canonical
        payload["instrument"] = metadata
        payload["snapshot_kind"] = "STALE_STREAM_CACHE"
        payload["stream_degraded"] = True
        payload["stale"] = True
        payload["snapshot_age_seconds"] = bridge_age_seconds
        payload["message"] = fallback_error
        payload["live_orders"] = False
        return payload
    return {
        "success": False,
        "source": "FYERS",
        "symbol": canonical,
        "snapshot": None,
        "message": (
            "FYERS live stream and REST quote are unavailable. "
            f"{fallback_error}"
        ),
        "stream_degraded": True,
        "live_orders": False,
    }


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = alpha * value + (1 - alpha) * current
    return current


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for previous, current in zip(values[-period - 1 : -1], values[-period:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss == 0:
        return 100.0
    rs = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    true_ranges = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        high = float(current["high"])
        low = float(current["low"])
        previous_close = float(previous["close"])
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sum(true_ranges) / len(true_ranges) if true_ranges else None


def _timeframe_evidence(symbol: str, timeframe: str) -> dict[str, Any]:
    payload = candles_payload(symbol, timeframe, 220)
    raw_candles = list(payload.get("candles") or [])
    candles = completed_candles(raw_candles, timeframe)
    if not payload.get("success") or len(candles) < 55:
        return {
            "timeframe": timeframe,
            "available": False,
            "message": payload.get("message") or "Market data unavailable.",
            "source": payload.get("source"),
            "raw_bars": len(raw_candles),
            "complete_bars": len(candles),
            "forming_bar_excluded": len(candles) < len(raw_candles),
        }

    closes = [float(row["close"]) for row in candles]
    volumes = [float(row.get("volume") or 0.0) for row in candles]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi14 = _rsi(closes, 14)
    atr14 = _atr(candles, 14)
    close = closes[-1]
    recent = candles[-20:]
    support = min(float(row["low"]) for row in recent)
    resistance = max(float(row["high"]) for row in recent)
    volume_mean = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
    volume_ratio = (volumes[-1] / volume_mean) if volume_mean > 0 else None

    if ema20 is None or ema50 is None:
        trend = "UNAVAILABLE"
    elif close > ema20 > ema50:
        trend = "BULLISH"
    elif close < ema20 < ema50:
        trend = "BEARISH"
    else:
        trend = "MIXED"

    from omni.trading_intelligence.quant_firm_engine import decide
    from workstation.unified_feature_engine import UNIFIED_FEATURE_ENGINE

    decision = decide(symbol, timeframe, candles).to_dict()
    decision["success"] = True
    interval_seconds = _TIMEFRAME_SECONDS.get(normalize_timeframe(timeframe), 300)
    try:
        last_open_epoch = float(candles[-1].get("time", candles[-1].get("timestamp")))
        last_close_epoch = float(candles[-1].get("close_time") or (last_open_epoch + interval_seconds))
        data_age_seconds = max(0.0, time.time() - last_close_epoch)
    except (TypeError, ValueError):
        data_age_seconds = None
    features = UNIFIED_FEATURE_ENGINE.analyze(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        provider=payload.get("source"),
        provider_symbol=payload.get("provider_symbol"),
        data_quality=payload.get("data_quality"),
        verified=bool(payload.get("success")),
        stale=bool(data_age_seconds is not None and data_age_seconds > interval_seconds * 3),
    )
    feature_storage = {
        "stored": False,
        "reason": "FEATURE_SNAPSHOT_NOT_VERIFIED_OR_FRESH",
        "paper_only": True,
        "live_execution": False,
    }
    if features.get("success") and features.get("data", {}).get("verified") and not features.get("data", {}).get("stale"):
        try:
            from workstation.multi_timeframe_feature_store import MULTI_TIMEFRAME_FEATURE_STORE

            feature_storage = MULTI_TIMEFRAME_FEATURE_STORE.record(features)
        except (OSError, ValueError) as error:
            feature_storage = {
                "stored": False,
                "reason": type(error).__name__,
                "paper_only": True,
                "live_execution": False,
            }
    patterns = dict(features.get("patterns") or {})
    journal_bars = []
    for candle in candles[-80:]:
        try:
            journal_bars.append(
                {
                    "time": candle.get("time", candle.get("timestamp")),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": float(candle.get("volume") or 0.0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return {
        "timeframe": timeframe,
        "available": True,
        "source": payload.get("source"),
        "data_quality": payload.get("data_quality"),
        "provider_symbol": payload.get("provider_symbol"),
        "close": close,
        "ema20": ema20,
        "ema50": ema50,
        "rsi14": rsi14,
        "atr14": atr14,
        "support": support,
        "resistance": resistance,
        "volume_ratio": volume_ratio,
        "trend": trend,
        "last_candle_time": candles[-1]["time"],
        "raw_bars": len(raw_candles),
        "complete_bars": len(candles),
        "forming_bar_excluded": len(candles) < len(raw_candles),
        "data_age_seconds": data_age_seconds,
        "fresh": data_age_seconds is None or data_age_seconds <= interval_seconds * 3,
        "decision": decision,
        "patterns": patterns,
        "features": features,
        # Bounded immutable completed-bar evidence for future journal replay.
        # It is stored only when a synthetic paper position is opened.
        "journal_bars": journal_bars,
        "feature_storage": feature_storage,
    }


def _decision_from_evidence(row: dict[str, Any], symbol: str) -> dict[str, Any]:
    """Return the strategy decision attached to a timeframe evidence row.

    The small trend-derived fallback keeps the public scan contract compatible
    with older integrations that supply evidence rows without a nested decision.
    Production evidence always carries the full Quant Firm decision.
    """

    decision = row.get("decision")
    if isinstance(decision, dict):
        return dict(decision)
    trend = str(row.get("trend") or "").upper()
    side = "LONG" if trend == "BULLISH" else "SHORT" if trend == "BEARISH" else "WAIT"
    close = row.get("close")
    atr = row.get("atr14")
    entry = stop = target = risk_reward = None
    if side in {"LONG", "SHORT"} and close is not None and atr:
        entry = float(close)
        distance = float(atr)
        stop = entry - distance if side == "LONG" else entry + distance
        target = entry + (2.0 * distance) if side == "LONG" else entry - (2.0 * distance)
        risk_reward = 2.0
    return {
        "success": bool(row.get("available")),
        "symbol": symbol,
        "timeframe": row.get("timeframe"),
        "regime": "TRENDING" if side != "WAIT" else "RANGE",
        "side": side,
        "score": 70.0 if side != "WAIT" else 0.0,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_reward": risk_reward,
        "votes": [],
        "evidence_graph": [],
        "contradictions": [],
        "reasons_not_to_trade": ["LEGACY_EVIDENCE_WITHOUT_REGISTERED_STRATEGY_SIGNAL"],
        "registry_versioned": False,
        "paper_only": True,
        "live_execution": False,
    }


def _paper_session_open(symbol: str) -> bool:
    try:
        from workstation.paper_market_data import PAPER_MARKET_DATA

        return bool(PAPER_MARKET_DATA.session_open(symbol))
    except Exception:
        # Fail closed for automatic entries when the calendar cannot be checked.
        return False


def _consensus_message(
    blockers: list[str],
    side: str,
    score: float,
    timeframes: tuple[str, ...],
) -> str:
    labels = {
        "INSUFFICIENT_TIMEFRAME_DATA": "fewer than two verified timeframes are available",
        "TIMEFRAME_DIRECTION_CONFLICT": "the selected timeframe strategy decisions disagree",
        "INSUFFICIENT_DIRECTIONAL_CONFIRMATION": "fewer than two timeframes confirm one direction",
        "ALIGNMENT_BELOW_GATE": "timeframe alignment is below the active profile gate",
        "SCORE_BELOW_GATE": "the strategy score is below the active profile gate",
        "REGIME_INCOMPATIBLE_SIGNAL": "no supporting strategy is compatible with the detected regime",
        "STRATEGY_VOTE_CONFLICT": "opposing registered strategy votes remain unresolved",
        "HIGHER_TIMEFRAME_TREND_CONFLICT": "15m or 1h trend evidence opposes the candidate",
        "ALL_TIMEFRAMES_RANGE": "all verified timeframes are range-bound",
        "PATTERN_NOT_CONFIRMED": "the selected single timeframe has no confirmed breakout or breakdown aligned with the strategy",
        "PATTERN_OR_STRATEGY_CONFIRMATION_REQUIRED": "neither timeframe has an aligned confirmed pattern or regime-compatible strategy vote",
        "INVALID_RISK_LEVELS": "verified entry, stop and target levels are unavailable",
        "RISK_REWARD_BELOW_GATE": "risk/reward is below 1.8 to 1",
        "MARKET_SESSION_CLOSED": "the configured market session is closed",
        "RESEARCH_ONLY_GLOBAL_FEED": "the global fallback feed is delayed/unofficial and excluded from automatic entries",
        "STALE_MARKET_DATA": "the latest completed market bar is stale",
    }
    if not blockers:
        return (
            f"Qualified {side} paper setup: {', '.join(timeframes)} consensus passed "
            f"direction, regime, score ({score:.1f}) and risk gates."
        )
    reasons = "; ".join(labels.get(item, item.replace("_", " ").lower()) for item in blockers)
    return f"WAIT. No automatic paper entry: {reasons}."


def _analysis_profile(value: str | None) -> tuple[str, tuple[str, ...]]:
    from workstation.trading_timeframe_profiles import resolve_trading_profile

    profile = resolve_trading_profile(value)
    return profile.name, profile.timeframes


def scan_payload(symbol: str, profile: str = "intraday") -> dict[str, Any]:
    from workstation.trading_timeframe_profiles import resolve_trading_profile

    canonical = normalize_symbol(symbol)
    profile_spec = resolve_trading_profile(profile)
    profile_name, consensus_timeframes = profile_spec.name, profile_spec.timeframes
    metadata = symbol_metadata(canonical)
    evidence = [_timeframe_evidence(canonical, tf) for tf in consensus_timeframes]
    available = [row for row in evidence if row.get("available")]
    if not available:
        return {
            "success": False,
            "symbol": canonical,
            "timeframe": " / ".join(consensus_timeframes),
            "profile": profile_name,
            "decision_version": "QUANT_ENSEMBLE_V2_GOVERNED_CONSENSUS_V4",
            "qualified": False,
            "side": "WAIT",
            "candidate_side": "WAIT",
            "score": 0.0,
            "bias": "NO DATA",
            "regime": "DATA UNAVAILABLE",
            "alignment": 0,
            "session_open": _paper_session_open(canonical),
            "blockers": ["INSUFFICIENT_TIMEFRAME_DATA"],
            "entry": None,
            "stop": None,
            "target": None,
            "risk_reward": None,
            "votes": [],
            "evidence_graph": [],
            "contradictions": [],
            "reasons_not_to_trade": ["INSUFFICIENT_TIMEFRAME_DATA"],
            "setup": None,
            "evidence": evidence,
            "decisions": [],
            "instrument": metadata,
            "profile_rules": profile_spec.to_dict(),
            "message": "No verified multi-timeframe market data is available.",
            "paper_only": True,
            "live_execution": False,
        }

    decisions = [_decision_from_evidence(row, canonical) for row in available]
    usable = [row for row in decisions if row.get("success")]
    directional = [row for row in usable if str(row.get("side") or "").upper() in {"LONG", "SHORT"}]
    sides = {str(row.get("side") or "").upper() for row in directional}
    candidate_side = next(iter(sides)) if len(sides) == 1 else "WAIT"
    confirming = [row for row in directional if str(row.get("side") or "").upper() == candidate_side]
    alignment = round(len(confirming) / max(len(usable), 1) * 100)
    score = (
        sum(float(row.get("score") or 0.0) for row in confirming) / len(confirming)
        if confirming
        else 0.0
    )

    pattern_rows = [
        (row, dict(row.get("patterns") or {}))
        for row in available
        if isinstance(row.get("patterns"), dict)
    ]
    pattern = pattern_rows[0][1] if pattern_rows else {}
    pattern_state = str(pattern.get("state") or "NO_EDGE").upper()
    pattern_direction = str(pattern.get("direction") or "NEUTRAL").upper()
    if profile_spec.single_timeframe and pattern.get("success") and confirming:
        score = 0.70 * score + 0.30 * float(pattern.get("score") or 0.0)

    anchor_order = (
        consensus_timeframes
        if profile_spec.single_timeframe
        else ("1d", "4h", "1h")
        if profile_name == "swing"
        else ("15m", "5m", "1h")
    )
    anchor = next(
        (
            row
            for tf in anchor_order
            for row in confirming
            if row.get("timeframe") == tf
            and row.get("entry") is not None
            and row.get("stop") is not None
            and row.get("target") is not None
        ),
        None,
    )
    risk_reward = float(anchor.get("risk_reward") or 0.0) if anchor else 0.0
    session_open = _paper_session_open(canonical)
    blockers: list[str] = []
    required_confirmations = 1 if profile_spec.single_timeframe else 2
    if len(usable) < required_confirmations:
        blockers.append("INSUFFICIENT_TIMEFRAME_DATA")
    if len(sides) > 1:
        blockers.append("TIMEFRAME_DIRECTION_CONFLICT")
    if len(confirming) < required_confirmations:
        blockers.append("INSUFFICIENT_DIRECTIONAL_CONFIRMATION")
    if alignment < profile_spec.minimum_alignment:
        blockers.append("ALIGNMENT_BELOW_GATE")
    if score < profile_spec.minimum_score:
        blockers.append("SCORE_BELOW_GATE")
    supporting_nodes = [
        node
        for row in confirming
        for node in (row.get("evidence_graph") or [])
        if str(node.get("side") or "").upper() == candidate_side
    ]
    if supporting_nodes and not any(node.get("regime_compatible") is not False for node in supporting_nodes):
        blockers.append("REGIME_INCOMPATIBLE_SIGNAL")
    if any(row.get("contradictions") for row in confirming):
        blockers.append("STRATEGY_VOTE_CONFLICT")

    trend_side = {"BULLISH": "LONG", "BEARISH": "SHORT"}
    higher_timeframes = set(consensus_timeframes[1:])
    if not profile_spec.single_timeframe and candidate_side in {"LONG", "SHORT"} and any(
        row.get("timeframe") in higher_timeframes
        and trend_side.get(str(row.get("trend") or "").upper()) not in {None, candidate_side}
        for row in available
    ):
        blockers.append("HIGHER_TIMEFRAME_TREND_CONFLICT")
    if (
        profile_name != "paper_exploration"
        and usable
        and all(str(row.get("regime") or "").upper() == "RANGE" for row in usable)
    ):
        blockers.append("ALL_TIMEFRAMES_RANGE")
    expected_pattern_direction = (
        "BULLISH" if candidate_side == "LONG" else "BEARISH" if candidate_side == "SHORT" else "NEUTRAL"
    )
    if profile_spec.require_confirmed_pattern:
        if pattern_state not in {"CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"} or pattern_direction != expected_pattern_direction:
            blockers.append("PATTERN_NOT_CONFIRMED")
    confirmed_pattern = next(
        (
            candidate_pattern
            for _, candidate_pattern in pattern_rows
            if candidate_pattern.get("success")
            and str(candidate_pattern.get("state") or "").upper()
            in {"CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"}
            and str(candidate_pattern.get("direction") or "").upper() == expected_pattern_direction
        ),
        None,
    )
    compatible_strategy = any(node.get("regime_compatible") is True for node in supporting_nodes)
    if profile_spec.require_pattern_or_strategy_confirmation and not (
        confirmed_pattern or compatible_strategy
    ):
        blockers.append("PATTERN_OR_STRATEGY_CONFIRMATION_REQUIRED")
    if confirmed_pattern is not None:
        pattern = confirmed_pattern
    if anchor is None:
        blockers.append("INVALID_RISK_LEVELS")
    elif risk_reward < profile_spec.minimum_risk_reward:
        blockers.append("RISK_REWARD_BELOW_GATE")
    if not session_open:
        blockers.append("MARKET_SESSION_CLOSED")
    elif any(row.get("fresh") is False for row in available):
        blockers.append("STALE_MARKET_DATA")
    if not metadata.get("auto_execution_eligible", True):
        blockers.append("RESEARCH_ONLY_GLOBAL_FEED")

    blockers = list(dict.fromkeys(blockers))
    qualified = not blockers and candidate_side in {"LONG", "SHORT"}
    analysis_blockers = [
        item for item in blockers if item not in {"MARKET_SESSION_CLOSED", "RESEARCH_ONLY_GLOBAL_FEED"}
    ]
    research_candidate = (
        not analysis_blockers and candidate_side in {"LONG", "SHORT"} and anchor is not None
    )
    side = candidate_side if qualified else "WAIT"
    bias = "BULLISH" if candidate_side == "LONG" else "BEARISH" if candidate_side == "SHORT" else "MIXED"
    regimes = {str(row.get("regime") or "").upper() for row in usable}
    regime = (
        "CONFLICT / WAIT"
        if "TIMEFRAME_DIRECTION_CONFLICT" in blockers
        else "RANGE / WAIT"
        if "ALL_TIMEFRAMES_RANGE" in blockers
        else "TRENDING"
        if "TRENDING" in regimes
        else "HIGH VOLATILITY"
        if "HIGH_VOLATILITY" in regimes
        else "MIXED / WAIT"
    )
    setup = None
    if research_candidate and anchor is not None:
        setup = {
            "side": bias,
            "entry_reference": float(anchor["entry"]),
            "stop_reference": float(anchor["stop"]),
            "target_reference": float(anchor["target"]),
            "risk_reward_reference": risk_reward,
            "status": "PAPER_QUALIFIED" if qualified else "CONDITIONAL_RESEARCH_ONLY",
            "timeframe": anchor.get("timeframe"),
            "executable_now": qualified,
        }
    votes = []
    evidence_graph = []
    contradictions = []
    for row in confirming:
        for vote in list(row.get("votes") or [])[:3]:
            enriched = dict(vote)
            enriched["timeframe"] = row.get("timeframe")
            votes.append(enriched)
    for row in usable:
        timeframe_label = row.get("timeframe")
        for node in list(row.get("evidence_graph") or []):
            enriched = dict(node)
            enriched["timeframe"] = timeframe_label
            evidence_graph.append(enriched)
        for contradiction in list(row.get("contradictions") or []):
            enriched = dict(contradiction)
            enriched["timeframe"] = timeframe_label
            contradictions.append(enriched)
    if len(sides) > 1:
        contradictions.append(
            {
                "reason": "opposing directional decisions across selected timeframes",
                "timeframes": [row.get("timeframe") for row in directional],
                "sides": [row.get("side") for row in directional],
            }
        )
    reasons_not_to_trade = list(blockers)
    if not qualified:
        for row in usable:
            reasons_not_to_trade.extend(list(row.get("reasons_not_to_trade") or []))
    reasons_not_to_trade = list(dict.fromkeys(reasons_not_to_trade))

    return {
        "success": True,
        "symbol": canonical,
        "timeframe": " / ".join(consensus_timeframes),
        "profile": profile_name,
        "decision_version": "QUANT_ENSEMBLE_V2_GOVERNED_CONSENSUS_V4",
        "qualified": qualified,
        "side": side,
        "candidate_side": candidate_side,
        "score": round(score, 2),
        "bias": bias,
        "regime": regime,
        "alignment": alignment,
        "session_open": session_open,
        "blockers": blockers,
        "research_candidate": research_candidate,
        "entry": float(anchor["entry"]) if research_candidate and anchor else None,
        "stop": float(anchor["stop"]) if research_candidate and anchor else None,
        "target": float(anchor["target"]) if research_candidate and anchor else None,
        "risk_reward": risk_reward if research_candidate else None,
        "risk_model": dict(anchor.get("risk_model") or {}) if research_candidate and anchor else None,
        "votes": votes,
        "evidence_graph": evidence_graph,
        "contradictions": contradictions,
        "reasons_not_to_trade": reasons_not_to_trade,
        "registry_versioned": all(bool(row.get("registry_versioned")) for row in usable),
        "setup": setup,
        "evidence": evidence,
        "decisions": decisions,
        "instrument": metadata,
        "profile_rules": profile_spec.to_dict(),
        "pattern_confirmation": pattern,
        "message": _consensus_message(blockers, candidate_side, score, consensus_timeframes),
        "paper_only": True,
        "live_execution": False,
    }


def _spawn_fyers_login() -> bool:
    from omni.runtime_paths import fyers_python

    python = fyers_python()
    if not python.exists():
        return False
    if os.name == "nt":
        command = (
            f'Set-Location -LiteralPath "{PROJECT_ROOT}"; '
            f'& "{python}" -m agents.fyers_auth_manager login'
        )
        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=str(PROJECT_ROOT),
            creationflags=int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0)),
        )
    else:
        subprocess.Popen(
            [str(python), "-m", "agents.fyers_auth_manager", "login"],
            cwd=str(PROJECT_ROOT),
        )
    return True


def _restart_market_bridge() -> dict[str, Any]:
    if not _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
        start_live_bridge()
    response = _bridge_request("/api/restart", method="POST", timeout=4.0)
    return response or provider_payload()


def start_paper_autonomy_on_boot() -> dict[str, Any]:
    if not AUTO_PAPER_START:
        return {
            "success": True,
            "running": False,
            "reason": "AUTO_START_DISABLED",
            "paper_only": True,
            "live_execution": False,
        }
    from workstation.paper_autonomy_engine import paper_autonomy

    return paper_autonomy.start()


def agent_payload(text: str) -> dict[str, Any]:
    from workstation.jarvis_trading_workstation_v7 import app as legacy
    from workstation.options_intelligence_router import options_command_payload
    from workstation.option_chart_data import attach_chart_directive
    from workstation.paper_trading_desk import paper_command_payload
    from workstation.paper_trade_action_router import paper_trade_action_payload
    from workstation.quant_signal_terminal import attach_signal_chart, signal_terminal_payload
    from workstation.nautilus_universe_router import universe_command_payload

    command = str(text or "").strip()

    from workstation.morning_trading_coordinator import morning_command_payload
    from workstation.multi_market_scanner import multi_market_scan_command_payload
    from workstation.nifty50_breakout_scanner import nifty50_scan_command_payload

    morning_result = morning_command_payload(command)
    if morning_result is not None:
        return morning_result

    universe_result = universe_command_payload(command)
    if universe_result is not None:
        return universe_result

    multi_scan_result = multi_market_scan_command_payload(command)
    if multi_scan_result is not None:
        return multi_scan_result

    nifty_scan_result = nifty50_scan_command_payload(command)
    if nifty_scan_result is not None:
        return nifty_scan_result

    option_result = options_command_payload(command)
    if option_result is not None:
        return attach_chart_directive(command, option_result)

    paper_result = paper_command_payload(command)
    if paper_result is not None:
        return paper_result

    trade_action = paper_trade_action_payload(command)
    if trade_action is not None:
        return attach_signal_chart(command, trade_action)

    signal_result = signal_terminal_payload(command)
    if signal_result is not None:
        return signal_result

    result = legacy.local_agent(command)
    if not result or (
        result.get("action") == "conversation_only"
        and "not wired" in str(result.get("speech") or "").lower()
    ):
        result = {
            "action": "open_master_chat",
            "text": command,
            "speech": "Opening this request in Master JARVIS Chat.",
        }
    result = dict(result)
    result["paper_only"] = True
    result["live_execution"] = False
    return result


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, default=_json_safe).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = parsed.path

        if path == "/":
            return self.send_file(STATIC / "index.html", "text/html; charset=utf-8")
        if path == "/intelligence.html":
            return self.send_file(STATIC / "intelligence.html", "text/html; charset=utf-8")
        if path == "/intelligence.js":
            return self.send_file(STATIC / "intelligence.js", "application/javascript; charset=utf-8")
        if path == "/intelligence.css":
            return self.send_file(STATIC / "intelligence.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self.send_file(STATIC / "app.js", "application/javascript; charset=utf-8")
        if path == "/lightweight-charts.standalone.production.js":
            return self.send_file(
                STATIC / "lightweight-charts.standalone.production.js",
                "application/javascript; charset=utf-8",
            )
        if path == "/session_hotfix.js":
            return self.send_file(STATIC / "session_hotfix.js", "application/javascript; charset=utf-8")
        if path == "/scan_consistency_hotfix.js":
            return self.send_file(STATIC / "scan_consistency_hotfix.js", "application/javascript; charset=utf-8")
        if path == "/option_chart_runtime.js":
            return self.send_file(STATIC / "option_chart_runtime.js", "application/javascript; charset=utf-8")
        if path == "/paper_desk_runtime.js":
            return self.send_file(STATIC / "paper_desk_runtime.js", "application/javascript; charset=utf-8")
        if path == "/nautilus_core_runtime.js":
            return self.send_file(STATIC / "nautilus_core_runtime.js", "application/javascript; charset=utf-8")
        if path == "/advanced_terminal_runtime.js":
            return self.send_file(STATIC / "advanced_terminal_runtime.js", "application/javascript; charset=utf-8")
        if path == "/style.css":
            return self.send_file(STATIC / "style.css", "text/css; charset=utf-8")
        if path == "/api/health":
            provider = provider_payload()
            provider_ready, provider_error = provider_health_state(provider)
            if provider_ready:
                HEALTH.mark_success()
            else:
                HEALTH.mark_error(provider_error or "FYERS_BRIDGE_DEGRADED")
            return self.send_json(
                HEALTH.payload(
                    status="READY" if provider_ready else "DEGRADED",
                    healthy=True,
                    dependencies={"fyers_bridge": "READY" if provider_ready else "DEGRADED"},
                    engine_ready=True,
                )
            )
        if path == "/api/provider":
            return self.send_json(provider_payload())
        if path == "/api/candles":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                timeframe = str((params.get("timeframe") or ["5m"])[0])
                bars = int((params.get("bars") or ["500"])[0])
                payload = candles_payload(symbol, timeframe, bars)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json({"success": False, "message": _safe_message(exc)}, 400)
        if path == "/api/option-candles":
            try:
                from workstation.option_chart_data import option_candles

                provider = str((params.get("provider") or [""])[0])
                instrument = str((params.get("instrument") or [""])[0])
                timeframe = str((params.get("timeframe") or ["5m"])[0])
                bars = int((params.get("bars") or ["500"])[0])
                payload = option_candles(provider, instrument, timeframe, bars)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json(
                    {
                        "success": False,
                        "paper_only": True,
                        "live_execution": False,
                        "message": _safe_message(exc),
                    },
                    400,
                )
        if path == "/api/option-live":
            try:
                from workstation.option_chart_data import option_live

                provider = str((params.get("provider") or [""])[0])
                instrument = str((params.get("instrument") or [""])[0])
                payload = option_live(provider, instrument)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json(
                    {
                        "success": False,
                        "paper_only": True,
                        "live_execution": False,
                        "message": _safe_message(exc),
                    },
                    400,
                )
        if path == "/api/live":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                payload = live_payload(symbol)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json({"success": False, "message": _safe_message(exc)}, 400)
        if path == "/api/paper/portfolio":
            from workstation.paper_trading_desk import portfolio_payload

            return self.send_json(portfolio_payload())
        if path == "/api/paper/autonomy":
            from workstation.paper_autonomy_engine import paper_autonomy

            return self.send_json(paper_autonomy.status())
        if path == "/api/paper/portfolio-controller":
            from workstation.paper_portfolio_controller import paper_portfolio_controller

            return self.send_json(paper_portfolio_controller.status())
        if path == "/api/equity/nifty50-scan":
            from workstation.nifty50_breakout_scanner import nifty50_scanner

            return self.send_json(nifty50_scanner.status())
        if path == "/api/scanner/multi":
            from workstation.multi_market_scanner import multi_market_scanner

            return self.send_json(multi_market_scanner.status())
        if path == "/api/paper/review":
            from workstation.bounded_decision_review import decision_review_coordinator

            return self.send_json(
                {
                    **decision_review_coordinator.status(),
                    "snapshot": decision_review_coordinator.snapshot(),
                }
            )
        if path == "/api/options/readiness":
            from workstation.options_readiness import options_readiness_payload

            return self.send_json(options_readiness_payload())
        if path == "/api/intelligence/module":
            from workstation.quant_intelligence_modules import intelligence_module_payload

            module = str((params.get("module") or [""])[0])
            symbol = str((params.get("symbol") or ["NIFTY"])[0])
            universe = str((params.get("universe") or [""])[0]) or None
            profile = str((params.get("profile") or ["intraday"])[0])
            expiry = str((params.get("expiry") or [""])[0]) or None
            payload = intelligence_module_payload(
                module,
                symbol,
                universe=universe,
                profile=profile,
                expiry=expiry,
            )
            return self.send_json(payload, 200 if payload.get("success") else 503)
        if path == "/api/scan":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                profile = str((params.get("profile") or ["intraday"])[0])
                payload = scan_payload(symbol, profile=profile)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json({"success": False, "message": _safe_message(exc)}, 400)
        if path == "/api/decision":
            try:
                from workstation.quant_firm_runtime import decision_payload

                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                timeframe = str((params.get("timeframe") or ["5m"])[0])
                payload = decision_payload(symbol, timeframe)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json(
                    {
                        "success": False,
                        "side": "WAIT",
                        "paper_only": True,
                        "live_execution": False,
                        "message": _safe_message(exc),
                    },
                    400,
                )
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            body = {}

        if path == "/api/paper/command":
            from workstation.paper_trading_desk import paper_command_payload

            text = str(body.get("text") or "").strip()
            payload = paper_command_payload(text)
            if payload is None:
                return self.send_json(
                    {
                        "success": False,
                        "message": "Unsupported paper-desk command.",
                        "paper_only": True,
                        "live_execution": False,
                    },
                    400,
                )
            return self.send_json(payload)
        if path == "/api/paper/autonomy/start":
            from workstation.paper_autonomy_engine import paper_autonomy

            return self.send_json(
                paper_autonomy.start(
                    profile=str(body.get("profile") or "") or None,
                    scan_now=bool(body.get("scan_now", True)),
                )
            )
        if path == "/api/paper/autonomy/stop":
            from workstation.paper_autonomy_engine import paper_autonomy

            return self.send_json(paper_autonomy.stop())
        if path == "/api/paper/portfolio-controller/start":
            from workstation.paper_portfolio_controller import paper_portfolio_controller

            requested = body.get("allocations")
            if isinstance(requested, dict):
                try:
                    paper_portfolio_controller.configure(requested)
                except ValueError as exc:
                    return self.send_json(
                        {
                            "success": False,
                            "message": str(exc),
                            "paper_only": True,
                            "live_execution": False,
                        },
                        400,
                    )
            return self.send_json(
                paper_portfolio_controller.start(
                    intraday_profile=str(body.get("profile") or "adaptive_intraday")
                )
            )
        if path == "/api/paper/portfolio-controller/stop":
            from workstation.paper_portfolio_controller import paper_portfolio_controller
            from workstation.multi_market_scanner import multi_market_scanner

            payload = paper_portfolio_controller.stop()
            return self.send_json(
                {**payload, "multi_market_scanner": multi_market_scanner.stop_monitoring()}
            )
        if path == "/api/equity/nifty50-scan/start":
            from workstation.nifty50_breakout_scanner import nifty50_scanner

            return self.send_json(
                nifty50_scanner.start(
                    force=bool(body.get("force", True)),
                    auto_enroll=bool(body.get("auto_enroll", False)),
                )
            )
        if path == "/api/scanner/multi/start":
            from workstation.multi_market_scanner import (
                DEFAULT_MORNING_UNIVERSES,
                multi_market_scanner,
            )

            requested = body.get("universes")
            universes = tuple(requested) if isinstance(requested, list) else DEFAULT_MORNING_UNIVERSES
            return self.send_json(
                multi_market_scanner.start(
                    universes=universes,
                    force=bool(body.get("force", True)),
                    auto_enroll=bool(body.get("auto_enroll", False)),
                    profile=str(body.get("profile") or "intraday"),
                )
            )
        if path == "/api/morning/start":
            from workstation.morning_trading_coordinator import (
                morning_command_payload,
                start_morning_paper_workflow,
            )

            text = str(body.get("text") or "").strip()
            if text:
                routed = morning_command_payload(text)
                if routed is not None:
                    return self.send_json(routed)
            requested = body.get("universes")
            universes = tuple(requested) if isinstance(requested, list) else None
            return self.send_json(
                start_morning_paper_workflow(
                    profile=str(body.get("profile") or "intraday"),
                    universes=universes,
                )
            )
        if path == "/api/agent":
            text = str(body.get("text") or "").strip()
            if not text:
                return self.send_json({"success": False, "message": "Empty command."}, 400)
            return self.send_json(agent_payload(text))
        if path == "/api/fyers/login":
            started = _spawn_fyers_login()
            return self.send_json(
                {
                    "success": started,
                    "message": (
                        "FYERS login opened in a local terminal. The App Secret remains local and hidden."
                        if started
                        else "The isolated FYERS Python environment is unavailable."
                    ),
                    "paper_only": True,
                    "live_execution": False,
                },
                200 if started else 503,
            )
        if path == "/api/market/restart":
            return self.send_json(_restart_market_bridge())
        self.send_error(404)

    def log_message(self, *_args) -> None:
        pass


def main() -> int:
    start_live_bridge()
    auto_status = start_paper_autonomy_on_boot()
    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE V5")
    print("=" * 72)
    print(f"Professional terminal: http://{HOST}:{PORT}")
    print("Charts: Lightweight Charts 5.x")
    print("Indian markets: FYERS read-only historical + live bridge")
    print("Crypto: public Binance market data")
    print("Mode: PAPER / RESEARCH")
    print(f"Automatic paper consensus: {'RUNNING' if auto_status.get('running') else 'STOPPED'}")
    print("Live broker execution: LOCKED")
    try:
        exclusive_server(HOST, PORT, Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
