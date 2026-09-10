"""Canonical market-data bus for the V16 terminal.

One cache key, one indicator computation, every consumer.

Blueprint section 3: chart, strategies, options, journal and the terminal must
all read the same verified evidence instead of each calling the provider. The
cache key therefore includes the *last completed candle*, so a new closed bar
invalidates the entry and nothing is ever served across a bar boundary.

This module never fetches anything itself and never upgrades an unverified
provider response into verified data. It only de-duplicates reads that have
already been certified elsewhere.
"""
from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

# Supported timeframes and their bar length. Kept local so this module has no
# import cycle with the Quant terminal that owns the provider read path.
TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "10m": 600,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}

# The venue determines the session calendar that decides whether a mark is
# tradable. It is part of the key because the same symbol name can be resolved
# on more than one venue.
VENUE_PREFIXES = {
    "NSE:": "NSE",
    "BSE:": "BSE",
    "MCX:": "MCX",
}
CRYPTO_SYMBOLS = {"BTC", "ETH", "SOL", "BNB", "XRP"}
MCX_SYMBOLS = {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}


def canonical_market(symbol: str, provider: str = "") -> str:
    """Resolve the market a symbol trades on, without guessing a venue."""

    text = str(symbol or "").strip().upper()
    provider_key = str(provider or "").strip().upper()
    if provider_key in {"BINANCE", "BINANCE_PUBLIC"} or text in CRYPTO_SYMBOLS:
        return "CRYPTO"
    for prefix, venue in VENUE_PREFIXES.items():
        if text.startswith(prefix):
            return venue
    if text in MCX_SYMBOLS:
        return "MCX"
    if text == "SENSEX":
        return "BSE"
    return "NSE"


def last_completed_candle(
    candles: Iterable[Mapping[str, Any]],
    timeframe: str,
    *,
    now_epoch: float | None = None,
) -> float | None:
    """Return the close time of the newest bar that has actually finished.

    A provider's still-forming final bar is excluded, so the key cannot change
    until a bar genuinely closes.
    """

    interval = TIMEFRAME_SECONDS.get(str(timeframe or "").strip().lower())
    if interval is None:
        return None
    now_value = float(now_epoch if now_epoch is not None else time.time())
    newest = None
    for row in candles or ():
        if not isinstance(row, Mapping):
            continue
        close_time = row.get("close_time")
        if close_time is None:
            opened = row.get("time", row.get("timestamp"))
            try:
                close_time = float(opened) + interval
            except (TypeError, ValueError):
                continue
        try:
            close_time = float(close_time)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close_time) or close_time > now_value:
            continue
        if newest is None or close_time > newest:
            newest = close_time
    return newest


def evidence_key(
    *,
    provider: str,
    market: str,
    instrument: str,
    timeframe: str,
    candle_close: float | None,
) -> tuple:
    """The one canonical cache key: provider, market, instrument, timeframe,
    last completed candle."""

    return (
        str(provider or "").strip().upper(),
        str(market or "").strip().upper(),
        str(instrument or "").strip().upper(),
        str(timeframe or "").strip().lower(),
        None if candle_close is None else round(float(candle_close), 3),
    )


class CanonicalMarketBus:
    """Single-flight cache above the provider read path.

    The bus never invents data. A loader that fails removes the entry and
    re-raises, so a stale value can never be mistaken for a fresh one.
    """

    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[tuple, threading.Event] = {}
        self.hits = 0
        self.misses = 0
        self.provider_loads = 0
        self.coalesced = 0

    def read(self, key: tuple, loader: Callable[[], Any], *, ttl: float = 5.0) -> Any:
        with self._lock:
            cached = self._entries.get(key)
            if cached and cached[0] > time.monotonic():
                self.hits += 1
                self._entries.move_to_end(key)
                return cached[1]
            event = self._inflight.get(key)
            owner = event is None
            if owner:
                if len(self._inflight) >= 32:
                    raise RuntimeError("MARKET_DATA_QUEUE_FULL")
                event = self._inflight[key] = threading.Event()
            else:
                self.coalesced += 1
        if not owner:
            # A second consumer waits for the single provider read rather than
            # issuing its own request. This is the fan-out protection.
            if not event.wait(30):
                raise TimeoutError("MARKET_DATA_COALESCED_READ_TIMEOUT")
            with self._lock:
                cached = self._entries.get(key)
            if cached:
                return cached[1]
            raise RuntimeError("MARKET_DATA_COALESCED_READ_FAILED")
        try:
            value = loader()
            with self._lock:
                self.misses += 1
                self.provider_loads += 1
                self._entries[key] = (time.monotonic() + max(ttl, 0.0), value)
                self._entries.move_to_end(key)
                while len(self._entries) > self.capacity:
                    self._entries.popitem(last=False)
            return value
        except BaseException:
            with self._lock:
                self._entries.pop(key, None)
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
                event.set()

    def invalidate(self, *, instrument: str | None = None) -> int:
        """Drop entries for one instrument, or everything when omitted."""

        target = str(instrument or "").strip().upper()
        with self._lock:
            if not target:
                removed = len(self._entries)
                self._entries.clear()
                return removed
            doomed = [k for k in self._entries if k[2] == target]
            for key in doomed:
                self._entries.pop(key, None)
            return len(doomed)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "inflight": len(self._inflight),
                "hits": self.hits,
                "misses": self.misses,
                "coalesced_reads": self.coalesced,
                "provider_loads": self.provider_loads,
                "capacity": self.capacity,
                "reuse_ratio": round(self.hits / max(self.hits + self.misses, 1), 4),
            }


MARKET_BUS = CanonicalMarketBus()


# --------------------------------------------------------------------------
# Indicators. Calculated once here; consumed by chart, strategies and options.
# --------------------------------------------------------------------------


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    alpha = 2.0 / (period + 1.0)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = alpha * value + (1 - alpha) * current
    return current


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains, losses = [], []
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


def atr(candles: list[Mapping[str, Any]], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    true_ranges = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        high = float(current["high"])
        low = float(current["low"])
        previous_close = float(previous["close"])
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sum(true_ranges) / len(true_ranges) if true_ranges else None


def vwap(candles: list[Mapping[str, Any]]) -> float | None:
    """Session VWAP using typical price weighted by volume."""

    numerator = denominator = 0.0
    for row in candles:
        try:
            typical = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3.0
            volume = float(row.get("volume") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        if volume <= 0:
            continue
        numerator += typical * volume
        denominator += volume
    return numerator / denominator if denominator > 0 else None


def _swing_levels(candles: list[Mapping[str, Any]], lookback: int = 40) -> tuple[float | None, float | None]:
    window = candles[-lookback:] if len(candles) > lookback else list(candles)
    if not window:
        return None, None
    try:
        highs = [float(r["high"]) for r in window]
        lows = [float(r["low"]) for r in window]
    except (KeyError, TypeError, ValueError):
        return None, None
    return (max(highs) if highs else None, min(lows) if lows else None)


def market_structure(candles: list[Mapping[str, Any]], lookback: int = 20) -> str:
    """Classify the recent swing sequence without predicting direction."""

    window = candles[-lookback:] if len(candles) > lookback else list(candles)
    if len(window) < 6:
        return "INSUFFICIENT_HISTORY"
    try:
        highs = [float(r["high"]) for r in window]
        lows = [float(r["low"]) for r in window]
    except (KeyError, TypeError, ValueError):
        return "INSUFFICIENT_HISTORY"
    mid = len(highs) // 2
    higher_highs = max(highs[mid:]) > max(highs[:mid])
    higher_lows = min(lows[mid:]) > min(lows[:mid])
    if higher_highs and higher_lows:
        return "UPTREND"
    if not higher_highs and not higher_lows:
        return "DOWNTREND"
    return "RANGE"


def volatility_regime(average_true_range: float | None, price: float | None) -> str:
    if not average_true_range or not price or price <= 0:
        return "UNKNOWN"
    ratio = average_true_range / price
    if ratio >= 0.02:
        return "HIGH_VOLATILITY"
    if ratio <= 0.005:
        return "COMPRESSED"
    return "NORMAL"


def indicator_bundle(
    candles: list[Mapping[str, Any]],
    *,
    price: float | None = None,
) -> dict[str, Any]:
    """Compute every shared indicator once for a completed-bar series.

    Returns a payload that always carries ``available`` and, when unavailable,
    an explicit ``reason``. Callers must treat an unavailable bundle as
    evidence-free; nothing here fabricates a value.
    """

    clean: list[dict[str, Any]] = []
    for row in candles or ():
        if not isinstance(row, Mapping):
            continue
        try:
            clean.append(
                {
                    "time": row.get("time", row.get("timestamp")),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0.0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if len(clean) < 20:
        return {"available": False, "reason": "INSUFFICIENT_COMPLETED_BARS", "complete_bars": len(clean)}

    closes = [row["close"] for row in clean]
    last = closes[-1]
    reference = float(price) if price and math.isfinite(float(price)) else last
    average_true_range = atr(clean)
    support, resistance = _swing_levels(clean)
    structure = market_structure(clean)
    session_vwap = vwap(clean)
    ema20, ema50 = ema(closes, 20), ema(closes, 50)
    volumes = [row["volume"] for row in clean]
    baseline = sum(volumes[-20:]) / min(len(volumes), 20) if volumes else 0.0
    return {
        "available": True,
        "as_of": clean[-1]["time"],
        "complete_bars": len(clean),
        "last_close": last,
        "ema20": ema20,
        "ema50": ema50,
        "rsi14": rsi(closes, 14),
        "atr14": average_true_range,
        "atr_pct": (average_true_range / reference * 100.0) if average_true_range and reference > 0 else None,
        "vwap": session_vwap,
        "vwap_position": None if session_vwap is None else ("ABOVE_VWAP" if reference >= session_vwap else "BELOW_VWAP"),
        "volume_ratio": (volumes[-1] / baseline) if baseline > 0 else None,
        "support": support,
        "resistance": resistance,
        "market_structure": structure,
        "regime": volatility_regime(average_true_range, reference),
    }


__all__ = [
    "TIMEFRAME_SECONDS",
    "CanonicalMarketBus",
    "MARKET_BUS",
    "canonical_market",
    "evidence_key",
    "indicator_bundle",
    "last_completed_candle",
    "market_structure",
    "volatility_regime",
]
