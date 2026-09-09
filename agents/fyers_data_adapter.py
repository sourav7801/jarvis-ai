"""Read-only FYERS API v3 market-data adapter.

The public result shape matches JARVIS' existing broker adapter so the trading
core can switch providers without changing strategy code. No order endpoints
are imported or exposed.

V15.1 hardening adds a cross-process provider governor because JARVIS analysis
runs FYERS history calls from the isolated .venv-fyers process. The governor is
strictly data-side: it serializes REST calls, caches recent successful history
snapshots, and fails closed during a verified FYERS 429 cooldown. It never
creates candles and never exposes broker order methods.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from agents.fyers_auth_manager import create_client, is_configured


INDIA_TZ = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]
_GOVERNOR_DIR = ROOT / "data" / "reliability" / "fyers_provider"
_GOVERNOR_STATE = _GOVERNOR_DIR / "state.json"
_GOVERNOR_LOCK = _GOVERNOR_DIR / "provider.lock"
_HISTORY_CACHE_DIR = _GOVERNOR_DIR / "history_cache"
_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_RATE_LIMIT_COOLDOWN_SECONDS = 65.0
_LOCK_STALE_SECONDS = 30.0

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


class FyersRateLimited(RuntimeError):
    def __init__(self, retry_after_seconds: float) -> None:
        self.retry_after_seconds = max(float(retry_after_seconds), 1.0)
        super().__init__(
            f"FYERS data API rate limited (429). Retry after about "
            f"{int(round(self.retry_after_seconds))} seconds."
        )


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


def _code_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _response_details(response: Any) -> dict[str, Any]:
    """Preserve FYERS' real provider code instead of guessing token expiry."""
    if not isinstance(response, dict):
        return {
            "provider_state": "PROVIDER_ERROR",
            "provider_code": None,
            "message": f"Invalid FYERS response: {type(response).__name__}",
            "retry_after_seconds": None,
        }
    code = _code_int(response.get("code"))
    raw_message = str(
        response.get("message")
        or response.get("msg")
        or response.get("code")
        or response.get("s")
        or "Unknown FYERS response"
    ).strip()
    if code == 429:
        return {
            "provider_state": "RATE_LIMITED",
            "provider_code": 429,
            "message": (
                "FYERS data API rate limited (429). JARVIS will cool down and "
                "retry through the governed data path; this does not imply an expired token."
            ),
            "retry_after_seconds": int(_RATE_LIMIT_COOLDOWN_SECONDS),
        }
    if code in {-403, 403}:
        return {
            "provider_state": "PERMISSION_REQUIRED",
            "provider_code": code,
            "message": "FYERS rejected this market-data request because required API permission is unavailable.",
            "retry_after_seconds": None,
        }
    if code == -5:
        return {
            "provider_state": "CREDENTIAL_MISMATCH",
            "provider_code": code,
            "message": "FYERS rejected the request because the application credentials/session do not match.",
            "retry_after_seconds": None,
        }
    if "token" in raw_message.lower() or "session" in raw_message.lower() or "auth" in raw_message.lower():
        state = "TOKEN_INVALID"
    elif raw_message.lower() == "bad request":
        state = "REQUEST_REJECTED"
    else:
        state = "PROVIDER_ERROR"
    return {
        "provider_state": state,
        "provider_code": code,
        "message": raw_message,
        "retry_after_seconds": None,
    }


def _response_error(response: Any) -> str:
    return str(_response_details(response)["message"])


def _ensure_governor_dirs() -> None:
    _HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_governor_state() -> dict[str, Any]:
    try:
        payload = json.loads(_GOVERNOR_STATE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(payload, default=str), encoding="utf-8")
    os.replace(temporary, path)


def _save_governor_state(payload: dict[str, Any]) -> None:
    _write_json_atomic(_GOVERNOR_STATE, payload)


@contextmanager
def _provider_lock(timeout_seconds: float = 20.0):
    """Cross-process lock for isolated FYERS workers using atomic file create."""
    _ensure_governor_dirs()
    deadline = time.monotonic() + max(float(timeout_seconds), 1.0)
    fd: int | None = None
    while time.monotonic() < deadline:
        try:
            fd = os.open(str(_GOVERNOR_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n{time.time()}".encode("ascii", errors="ignore"))
            break
        except FileExistsError:
            try:
                if time.time() - _GOVERNOR_LOCK.stat().st_mtime > _LOCK_STALE_SECONDS:
                    _GOVERNOR_LOCK.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            time.sleep(0.05)
    if fd is None:
        raise RuntimeError("FYERS provider governor lock timed out.")
    try:
        yield
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            _GOVERNOR_LOCK.unlink(missing_ok=True)
        except OSError:
            pass


def _governed_provider_call(call: Callable[[], Any]) -> Any:
    """Serialize provider REST calls and enforce a shared 429 cooldown."""
    with _provider_lock():
        state = _load_governor_state()
        now = time.time()
        cooldown_until = float(state.get("cooldown_until_epoch") or 0.0)
        if cooldown_until > now:
            raise FyersRateLimited(cooldown_until - now)
        last_request = float(state.get("last_request_epoch") or 0.0)
        wait = _MIN_REQUEST_INTERVAL_SECONDS - (now - last_request)
        if wait > 0:
            time.sleep(wait)
        response = call()
        finished = time.time()
        details = _response_details(response)
        state["last_request_epoch"] = finished
        state["last_provider_code"] = details.get("provider_code")
        state["last_provider_state"] = details.get("provider_state")
        if details.get("provider_code") == 429:
            state["cooldown_until_epoch"] = finished + _RATE_LIMIT_COOLDOWN_SECONDS
        elif float(state.get("cooldown_until_epoch") or 0.0) <= finished:
            state["cooldown_until_epoch"] = 0.0
        _save_governor_state(state)
        return response


def _cache_ttl_seconds(resolution: str) -> float:
    if resolution.isdigit():
        minutes = max(int(resolution), 1)
        return max(20.0, min(90.0, minutes * 8.0))
    if resolution == "1W":
        return 900.0
    return 300.0


def _history_cache_path(provider_symbol: str, resolution: str, bars: int) -> Path:
    raw = f"{provider_symbol}|{resolution}|{int(bars)}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return _HISTORY_CACHE_DIR / f"{digest}.json"


def _frame_to_cache_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    table = frame.reset_index()
    rows: list[dict[str, Any]] = []
    for record in table.to_dict(orient="records"):
        clean: dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                clean[str(key)] = value.isoformat()
            elif hasattr(value, "item"):
                try:
                    clean[str(key)] = value.item()
                except Exception:
                    clean[str(key)] = str(value)
            else:
                clean[str(key)] = value
        rows.append(clean)
    return rows


def _cache_rows_to_frame(rows: Any) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame = pd.DataFrame(rows)
    if "Timestamp" not in frame.columns:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], errors="coerce")
    for column in ("Open", "High", "Low", "Close", "Volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return (
        frame.dropna(subset=["Timestamp", "Open", "High", "Low", "Close"])
        .sort_values("Timestamp")
        .set_index("Timestamp")
    )


def _load_history_cache(provider_symbol: str, resolution: str, bars: int) -> pd.DataFrame | None:
    path = _history_cache_path(provider_symbol, resolution, bars)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - float(payload.get("saved_at_epoch") or 0.0)
        if age < 0 or age > _cache_ttl_seconds(resolution):
            return None
        frame = _cache_rows_to_frame(payload.get("rows"))
        return frame.tail(bars) if not frame.empty else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _save_history_cache(provider_symbol: str, resolution: str, bars: int, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    _write_json_atomic(
        _history_cache_path(provider_symbol, resolution, bars),
        {
            "saved_at_epoch": time.time(),
            "provider_symbol": provider_symbol,
            "resolution": resolution,
            "bars": int(bars),
            "rows": _frame_to_cache_rows(frame.tail(bars)),
        },
    )


def candles_to_frame(rows: list[list[Any]]) -> pd.DataFrame:
    valid = [row[:6] for row in rows if isinstance(row, (list, tuple)) and len(row) >= 6]
    if not valid:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame = pd.DataFrame(valid, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], unit="s", utc=True, errors="coerce").dt.tz_convert(INDIA_TZ)
    for column in ("Open", "High", "Low", "Close", "Volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["Timestamp", "Open", "High", "Low", "Close"])
    return frame.drop_duplicates(subset=["Timestamp"], keep="last").sort_values("Timestamp").set_index("Timestamp")


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
        return {"success": False, "source": "FYERS", "message": "The FYERS adapter currently supports Indian markets only."}
    if bars <= 0:
        return {"success": False, "source": "FYERS", "message": "bars must be greater than zero."}
    try:
        provider_symbol = normalize_symbol(symbol)
        resolution = resolution_for(timeframe)
    except ValueError as exc:
        return {"success": False, "source": "FYERS", "message": str(exc), "bars": 0, "data": None}
    if client is None and not is_configured():
        return {
            "success": False,
            "source": "FYERS",
            "provider_state": "LOGIN_REQUIRED",
            "message": "FYERS is not configured. Set FYERS_APP_ID and run python -m agents.fyers_auth_manager login.",
            "bars": 0,
            "data": None,
        }

    cached = _load_history_cache(provider_symbol, resolution, bars)
    if cached is not None:
        return {
            "success": True,
            "source": "FYERS",
            "data_quality": "BROKER_HISTORICAL",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": len(cached),
            "data": cached,
            "message": "Historical candles loaded from the bounded FYERS completed-history cache.",
            "provider_state": "READY",
            "provider_code": 200,
            "provider_cache_hit": True,
            "market_data_fabricated": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    try:
        fyers = client or create_client()
        end = datetime.now(INDIA_TZ).date()
        start = end - timedelta(days=_calendar_days_for_bars(bars, resolution))
        max_days = 100 if resolution.isdigit() else 366
        rows: list[list[Any]] = []
        errors: list[dict[str, Any]] = []
        for range_from, range_to in _windows(start, end, max_days):
            try:
                response = _governed_provider_call(
                    lambda rf=range_from, rt=range_to: fyers.history(
                        data={
                            "symbol": provider_symbol,
                            "resolution": resolution,
                            "date_format": "1",
                            "range_from": rf.isoformat(),
                            "range_to": rt.isoformat(),
                            "cont_flag": "1",
                        }
                    )
                )
            except FyersRateLimited as exc:
                errors.append({
                    "provider_state": "RATE_LIMITED",
                    "provider_code": 429,
                    "message": str(exc),
                    "retry_after_seconds": int(round(exc.retry_after_seconds)),
                })
                break
            if isinstance(response, dict) and response.get("s") == "ok":
                rows.extend(response.get("candles") or [])
            elif isinstance(response, dict) and response.get("s") == "no_data":
                continue
            else:
                details = _response_details(response)
                errors.append(details)
                if details.get("provider_state") == "RATE_LIMITED":
                    break

        frame = candles_to_frame(rows).tail(bars)
        if frame.empty:
            details = errors[-1] if errors else {
                "provider_state": "NO_DATA",
                "provider_code": None,
                "message": "FYERS returned no candles.",
                "retry_after_seconds": None,
            }
            return {
                "success": False,
                "source": "FYERS",
                "data_quality": "UNAVAILABLE",
                "symbol": requested_symbol,
                "provider_symbol": provider_symbol,
                "timeframe": timeframe,
                "bars": 0,
                "data": None,
                **details,
                "market_data_fabricated": False,
            }

        _save_history_cache(provider_symbol, resolution, bars, frame)
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
            "provider_state": "READY",
            "provider_code": 200,
            "provider_cache_hit": False,
            "provider_warnings": errors,
            "market_data_fabricated": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except FyersRateLimited as exc:
        return {
            "success": False,
            "source": "FYERS",
            "data_quality": "UNAVAILABLE",
            "symbol": requested_symbol,
            "provider_symbol": provider_symbol,
            "timeframe": timeframe,
            "bars": 0,
            "data": None,
            "provider_state": "RATE_LIMITED",
            "provider_code": 429,
            "retry_after_seconds": int(round(exc.retry_after_seconds)),
            "message": str(exc),
            "market_data_fabricated": False,
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
            "provider_state": "PROVIDER_ERROR",
            "provider_code": None,
            "message": str(exc),
            "market_data_fabricated": False,
        }


def get_quote(symbol: str, *, client: Any = None) -> dict[str, Any]:
    provider_symbol = ""
    try:
        provider_symbol = normalize_symbol(symbol)
        fyers = client or create_client()
        response = _governed_provider_call(lambda: fyers.quotes(data={"symbols": provider_symbol}))
        items = response.get("d", []) if isinstance(response, dict) else []
        if not items:
            details = _response_details(response)
            return {
                "success": False,
                "source": "FYERS",
                "symbol": str(symbol or "").strip().upper(),
                "provider_symbol": provider_symbol,
                **details,
            }
        item = items[0]
        values = item.get("v", {}) if isinstance(item, dict) else {}
        return {
            "success": True,
            "source": "FYERS",
            "symbol": str(symbol).strip().upper(),
            "provider_symbol": provider_symbol,
            "provider_state": "READY",
            "provider_code": 200,
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
    except FyersRateLimited as exc:
        return {
            "success": False,
            "source": "FYERS",
            "symbol": str(symbol or "").strip().upper(),
            "provider_symbol": provider_symbol or None,
            "provider_state": "RATE_LIMITED",
            "provider_code": 429,
            "retry_after_seconds": int(round(exc.retry_after_seconds)),
            "message": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "source": "FYERS",
            "symbol": str(symbol or "").strip().upper(),
            "provider_symbol": provider_symbol or None,
            "provider_state": "PROVIDER_ERROR",
            "provider_code": None,
            "message": str(exc),
        }


def provider_governor_status() -> dict[str, Any]:
    state = _load_governor_state()
    now = time.time()
    cooldown_until = float(state.get("cooldown_until_epoch") or 0.0)
    return {
        "success": True,
        "service": "JARVIS_FYERS_DATA_GOVERNOR_V151",
        "cross_process_serialization": True,
        "minimum_request_interval_seconds": _MIN_REQUEST_INTERVAL_SECONDS,
        "rate_limit_cooldown_seconds": _RATE_LIMIT_COOLDOWN_SECONDS,
        "rate_limited": cooldown_until > now,
        "retry_after_seconds": max(0, int(round(cooldown_until - now))),
        "last_provider_code": state.get("last_provider_code"),
        "last_provider_state": state.get("last_provider_state"),
        "history_cache": True,
        "market_data_fabricated": False,
        "read_only": True,
        "live_orders": False,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Test JARVIS FYERS market data")
    parser.add_argument("--symbol", default="NIFTY")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--bars", type=int, default=20)
    parser.add_argument("--quote", action="store_true")
    args = parser.parse_args(argv)
    result = get_quote(args.symbol) if args.quote else get_intraday_data(args.symbol, timeframe=args.timeframe, bars=args.bars)
    printable = {key: value for key, value in result.items() if key != "data"}
    print(printable)
    if result.get("success") and result.get("data") is not None:
        print(result["data"].tail())
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
