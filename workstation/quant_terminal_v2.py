from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC = PROJECT_ROOT / "workstation" / "quant_terminal_v2_static"
HOST = os.getenv("JARVIS_WORKSTATION_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_WORKSTATION_PORT", "8787"))
LIVE_BRIDGE_HOST = os.getenv("JARVIS_FYERS_BRIDGE_HOST", "127.0.0.1")
LIVE_BRIDGE_PORT = int(os.getenv("JARVIS_FYERS_BRIDGE_PORT", "8790"))
LIVE_BRIDGE_URL = f"http://{LIVE_BRIDGE_HOST}:{LIVE_BRIDGE_PORT}"

CRYPTO_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
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

_LIVE_BRIDGE_PROCESS: subprocess.Popen | None = None


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
    symbol = str(value or "").strip().upper().replace(" ", "")
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
    if result not in SUPPORTED_SYMBOLS:
        raise ValueError(f"Unsupported Quant Terminal symbol: {value}")
    return result


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


def _fyers_candles(symbol: str, timeframe: str, bars: int) -> dict[str, Any]:
    from workstation.fyers_isolated_history_bridge import get_intraday_data_isolated_frame

    result = get_intraday_data_isolated_frame(
        symbol,
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
        "provider_symbol": payload.get("provider_symbol") or symbol,
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
    return _fyers_candles(canonical, resolved_timeframe, bounded_bars)


def _bridge_request(path: str, method: str = "GET", timeout: float = 1.5) -> dict[str, Any] | None:
    data = b"{}" if method == "POST" else None
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

    fyers_python = PROJECT_ROOT / ".venv-fyers" / "Scripts" / "python.exe"
    if not fyers_python.exists():
        return False

    flags = 0
    if os.name == "nt":
        flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    try:
        _LIVE_BRIDGE_PROCESS = subprocess.Popen(
            [str(fyers_python), "-m", "workstation.fyers_live_bridge_service"],
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
    if bridge and bridge.get("connected"):
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

    if not _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
        start_live_bridge()
    payload = _bridge_request(
        "/api/snapshot?" + urllib.parse.urlencode({"symbol": canonical}),
        timeout=1.2,
    )
    if payload:
        payload["live_orders"] = False
        return payload
    return {
        "success": False,
        "source": "FYERS",
        "symbol": canonical,
        "snapshot": None,
        "message": "FYERS live snapshot unavailable. Refresh the FYERS data session if needed.",
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
    candles = payload.get("candles") or []
    if not payload.get("success") or len(candles) < 55:
        return {
            "timeframe": timeframe,
            "available": False,
            "message": payload.get("message") or "Market data unavailable.",
            "source": payload.get("source"),
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
    }


def scan_payload(symbol: str) -> dict[str, Any]:
    canonical = normalize_symbol(symbol)
    evidence = [_timeframe_evidence(canonical, tf) for tf in ("5m", "15m", "1h")]
    available = [row for row in evidence if row.get("available")]
    if not available:
        return {
            "success": False,
            "symbol": canonical,
            "bias": "NO DATA",
            "regime": "DATA UNAVAILABLE",
            "alignment": 0,
            "setup": None,
            "evidence": evidence,
            "message": "No verified multi-timeframe market data is available.",
            "paper_only": True,
            "live_execution": False,
        }

    bullish = sum(row.get("trend") == "BULLISH" for row in available)
    bearish = sum(row.get("trend") == "BEARISH" for row in available)
    total = len(available)
    alignment = round(max(bullish, bearish) / total * 100)
    if bullish > bearish:
        bias = "BULLISH"
    elif bearish > bullish:
        bias = "BEARISH"
    else:
        bias = "MIXED"

    anchor = next((row for row in available if row["timeframe"] == "15m"), available[0])
    atr = anchor.get("atr14")
    close = anchor.get("close")
    setup = None
    if alignment >= 67 and atr and close:
        if bias == "BULLISH":
            stop = close - atr
            target = close + (2 * atr)
        elif bias == "BEARISH":
            stop = close + atr
            target = close - (2 * atr)
        else:
            stop = target = None
        if stop is not None and target is not None:
            setup = {
                "side": bias,
                "entry_reference": close,
                "stop_reference": stop,
                "target_reference": target,
                "risk_reward_reference": 2.0,
                "status": "RESEARCH_CANDIDATE",
            }

    regime = "TRENDING" if alignment >= 67 and bias in {"BULLISH", "BEARISH"} else "MIXED / RANGE"
    return {
        "success": True,
        "symbol": canonical,
        "bias": bias,
        "regime": regime,
        "alignment": alignment,
        "setup": setup,
        "evidence": evidence,
        "message": (
            "Multi-timeframe research candidate generated."
            if setup
            else "No setup passed the current multi-timeframe alignment gate."
        ),
        "paper_only": True,
        "live_execution": False,
    }


def _spawn_fyers_login() -> bool:
    fyers_python = PROJECT_ROOT / ".venv-fyers" / "Scripts" / "python.exe"
    if not fyers_python.exists():
        return False
    if os.name == "nt":
        command = (
            f'Set-Location -LiteralPath "{PROJECT_ROOT}"; '
            f'& "{fyers_python}" -m agents.fyers_auth_manager login'
        )
        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=str(PROJECT_ROOT),
            creationflags=int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0)),
        )
    else:
        subprocess.Popen(
            [str(fyers_python), "-m", "agents.fyers_auth_manager", "login"],
            cwd=str(PROJECT_ROOT),
        )
    return True


def _restart_market_bridge() -> dict[str, Any]:
    if not _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):
        start_live_bridge()
    response = _bridge_request("/api/restart", method="POST", timeout=4.0)
    return response or provider_payload()


def agent_payload(text: str) -> dict[str, Any]:
    from workstation.jarvis_trading_workstation_v7 import app as legacy

    command = str(text or "").strip()
    result = legacy.local_agent(command) or {
        "action": "conversation_only",
        "speech": "That request is not wired to a deterministic trading action yet.",
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
        if path == "/app.js":
            return self.send_file(STATIC / "app.js", "application/javascript; charset=utf-8")
        if path == "/style.css":
            return self.send_file(STATIC / "style.css", "text/css; charset=utf-8")
        if path == "/api/health":
            return self.send_json(
                {
                    "ok": True,
                    "version": "QUANT_TERMINAL_V2",
                    "paper_only": True,
                    "live_execution": False,
                }
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
        if path == "/api/live":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                payload = live_payload(symbol)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json({"success": False, "message": _safe_message(exc)}, 400)
        if path == "/api/scan":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                payload = scan_payload(symbol)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json({"success": False, "message": _safe_message(exc)}, 400)
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            body = {}

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
    print("=" * 72)
    print("JARVIS QUANT TRADING INTELLIGENCE V2")
    print("=" * 72)
    print(f"Professional terminal: http://{HOST}:{PORT}")
    print("Charts: Lightweight Charts 5.x")
    print("Indian markets: FYERS read-only historical + live bridge")
    print("Crypto: public Binance market data")
    print("Mode: PAPER / RESEARCH")
    print("Live broker execution: LOCKED")
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
