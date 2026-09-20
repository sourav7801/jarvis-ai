from __future__ import annotations

"""Read-only fast display history for V17.4+.

This module never calls FYERS.  It only reads history snapshots that were
already written by the canonical FYERS adapter.  The result is explicitly
DISPLAY ONLY and therefore cannot become strategy/execution evidence.

Purpose:
- workspace navigation should never wait behind the FYERS provider governor;
- closed-market/weekend charts should render the last verified history at once;
- strategy engines continue to use the normal fresh/stale hard-gated path.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import threading
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "reliability" / "fyers_provider" / "history_cache"

RESOLUTIONS = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "1d": "D",
}

_SCAN_LOCK = threading.Lock()
_INDEX_AT = 0.0
_INDEX: dict[tuple[str, str], Path] = {}
_INDEX_REFRESH_SECONDS = 5.0


def _canonical_path(provider_symbol: str, resolution: str) -> Path:
    raw = f"{provider_symbol}|{resolution}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def _safe_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _rebuild_index() -> None:
    global _INDEX_AT, _INDEX
    now = time.monotonic()
    with _SCAN_LOCK:
        if now - _INDEX_AT < _INDEX_REFRESH_SECONDS:
            return
        index: dict[tuple[str, str], tuple[float, Path]] = {}
        try:
            files = list(CACHE_DIR.glob("*.json"))
        except OSError:
            files = []
        for path in files:
            payload = _safe_json(path)
            if not payload:
                continue
            provider_symbol = str(payload.get("provider_symbol") or "").strip().upper()
            resolution = str(payload.get("resolution") or "").strip().upper()
            if not provider_symbol or not resolution:
                continue
            try:
                saved = float(payload.get("saved_at_epoch") or path.stat().st_mtime)
            except (OSError, TypeError, ValueError):
                saved = 0.0
            key = (provider_symbol, resolution)
            previous = index.get(key)
            if previous is None or saved > previous[0]:
                index[key] = (saved, path)
        _INDEX = {key: value[1] for key, value in index.items()}
        _INDEX_AT = now


def _cache_path(provider_symbol: str, resolution: str) -> Path | None:
    canonical = _canonical_path(provider_symbol, resolution)
    if canonical.exists():
        return canonical
    _rebuild_index()
    return _INDEX.get((str(provider_symbol).upper(), str(resolution).upper()))


def _timestamp_seconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        if number > 10_000_000_000:
            number /= 1000.0
        return int(number)
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        number = None
    if number is not None and math.isfinite(number):
        if number > 10_000_000_000:
            number /= 1000.0
        return int(number)
    try:
        normalized = text.replace("Z", "+00:00")
        stamp = datetime.fromisoformat(normalized)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return int(stamp.timestamp())
    except ValueError:
        return None


def _row_value(row: dict[str, Any], name: str) -> Any:
    direct = row.get(name)
    if direct is not None:
        return direct
    lowered = name.lower()
    for key, value in row.items():
        if str(key).strip().lower() == lowered:
            return value
    return None


def _rows_to_candles(rows: Any, bars: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    candles: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp = None
        for candidate in ("Timestamp", "timestamp", "time", "datetime", "date"):
            timestamp = _timestamp_seconds(_row_value(row, candidate))
            if timestamp is not None:
                break
        if timestamp is None:
            continue
        try:
            candle = {
                "time": timestamp,
                "timestamp": timestamp,
                "open": float(_row_value(row, "Open")),
                "high": float(_row_value(row, "High")),
                "low": float(_row_value(row, "Low")),
                "close": float(_row_value(row, "Close")),
                "volume": float(_row_value(row, "Volume") or 0.0),
            }
        except (TypeError, ValueError):
            continue
        if all(math.isfinite(candle[key]) for key in ("open", "high", "low", "close", "volume")):
            candles.append(candle)
    candles.sort(key=lambda row: row["time"])
    requested = max(1, int(bars))
    return candles[-requested:]


def _fresh_ttl_seconds(timeframe: str) -> float:
    value = str(timeframe or "").lower()
    if value == "1d":
        return 1800.0
    if value in {"4h", "2h", "1h"}:
        return 300.0
    if value in {"30m", "15m"}:
        return 120.0
    return 60.0


def load_verified_history_snapshot(
    provider_symbol: str,
    timeframe: str,
    bars: int,
    *,
    max_display_age_seconds: float = 7 * 24 * 60 * 60,
) -> dict[str, Any]:
    """Return a verified persisted history snapshot for chart display only."""

    provider = str(provider_symbol or "").strip().upper()
    resolution = RESOLUTIONS.get(str(timeframe or "").strip().lower())
    if not provider or not resolution:
        return {
            "success": False,
            "reason": "DISPLAY_CACHE_IDENTITY_UNAVAILABLE",
            "display_only": True,
        }

    path = _cache_path(provider, resolution)
    if path is None:
        return {
            "success": False,
            "reason": "DISPLAY_CACHE_MISS",
            "provider_symbol": provider,
            "timeframe": timeframe,
            "display_only": True,
        }

    payload = _safe_json(path)
    if not payload:
        return {
            "success": False,
            "reason": "DISPLAY_CACHE_INVALID",
            "provider_symbol": provider,
            "timeframe": timeframe,
            "display_only": True,
        }

    try:
        age = max(0.0, time.time() - float(payload.get("saved_at_epoch") or 0.0))
    except (TypeError, ValueError):
        age = float("inf")
    if age > max(float(max_display_age_seconds), 0.0):
        return {
            "success": False,
            "reason": "DISPLAY_CACHE_TOO_OLD",
            "provider_symbol": provider,
            "timeframe": timeframe,
            "cache_age_seconds": age,
            "display_only": True,
        }

    candles = _rows_to_candles(payload.get("rows"), bars)
    if not candles:
        return {
            "success": False,
            "reason": "DISPLAY_CACHE_EMPTY",
            "provider_symbol": provider,
            "timeframe": timeframe,
            "cache_age_seconds": age,
            "display_only": True,
        }

    stale = age > _fresh_ttl_seconds(timeframe)
    return {
        "success": True,
        "source": "FYERS_VERIFIED_HISTORY_CACHE",
        "data_quality": (
            "BROKER_HISTORICAL_DISPLAY_STALE"
            if stale
            else "BROKER_HISTORICAL_DISPLAY_CACHE"
        ),
        "provider_symbol": provider,
        "timeframe": timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": (
            "Last verified FYERS history snapshot loaded instantly for chart display. "
            "It is not execution evidence."
        ),
        "provider_cache_hit": True,
        "provider_cache_stale": stale,
        "stale": stale,
        "display_only": True,
        "execution_eligible": False,
        "cache_age_seconds": round(age, 3),
        "cache_path_kind": (
            "CANONICAL_SYMBOL_TIMEFRAME"
            if path == _canonical_path(provider, resolution)
            else "LEGACY_DISCOVERED"
        ),
        "paper_only": True,
        "live_execution": False,
    }
