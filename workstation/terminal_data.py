"""Bounded shared reads and strict live-quote/candle validation."""
from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
from zoneinfo import ZoneInfo
import math
import threading
import time

from workstation.market_data_contract import VENUE_SESSIONS, _aware_timestamp


class SingleFlightCache:
    def __init__(self, capacity=256):
        self.capacity = capacity
        self._lock = threading.Lock()
        self._values = OrderedDict()
        self._pending = {}
        self.hits = self.loads = 0

    def get(self, key, loader, ttl=5.):
        with self._lock:
            cached = self._values.get(key)
            if cached and time.monotonic() < cached[0]:
                self.hits += 1
                self._values.move_to_end(key)
                return deepcopy(cached[1])
            event = self._pending.get(key)
            owner = event is None
            if owner:
                if len(self._pending) >= 32:
                    raise RuntimeError("MARKET_DATA_QUEUE_FULL")
                event = self._pending[key] = threading.Event()
        if not owner:
            if not event.wait(20):
                raise TimeoutError("SHARED_MARKET_READ_TIMEOUT")
            with self._lock:
                cached = self._values.get(key)
                if cached:
                    return deepcopy(cached[1])
            raise RuntimeError("SHARED_MARKET_READ_FAILED")
        try:
            result = loader()
            with self._lock:
                self.loads += 1
                self._values[key] = (time.monotonic() + ttl, deepcopy(result))
                self._values.move_to_end(key)
                while len(self._values) > self.capacity:
                    self._values.popitem(last=False)
            return result
        except BaseException:
            with self._lock:
                self._values.pop(key, None)
            raise
        finally:
            with self._lock:
                self._pending.pop(key, None)
                event.set()

    def status(self):
        with self._lock:
            return {"entries": len(self._values), "pending": len(self._pending), "cache_hits": self.hits, "provider_loads": self.loads, "capacity": self.capacity}


MARKET_CACHE = SingleFlightCache()
CACHE_ENABLED = False


def shared_read(ttl):
    def decorate(fn):
        @wraps(fn)
        def read(*args, **kwargs):
            if not CACHE_ENABLED:
                return fn(*args, **kwargs)
            key = (fn.__module__, fn.__name__, repr(args), repr(sorted(kwargs.items())))
            return MARKET_CACHE.get(key, lambda: fn(*args, **kwargs), ttl)
        return read
    return decorate


class BoundedPool:
    def __init__(self, workers=4, capacity=24):
        self.workers, self.capacity = workers, capacity
        self._slots = threading.BoundedSemaphore(capacity)
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="JarvisAnalysis")

    def submit(self, fn, *args):
        if not self._slots.acquire(timeout=.1):
            raise RuntimeError("ANALYSIS_QUEUE_FULL")
        try:
            future = self._pool.submit(fn, *args)
            future.add_done_callback(lambda _: self._slots.release())
            return future
        except BaseException:
            self._slots.release()
            raise


ANALYSIS_POOL = BoundedPool()


def scan_rows(fn, symbols, cancelled):
    # At most two outstanding jobs per lane, four executing across all lanes.
    pending = []
    for symbol in symbols:
        if cancelled.is_set():
            break
        try:
            pending.append((symbol, ANALYSIS_POOL.submit(fn, symbol)))
        except RuntimeError as exc:
            yield {"success": False, "symbol": symbol, "message": str(exc)}
        if len(pending) >= 2:
            name, future = pending.pop(0)
            try:
                yield future.result(timeout=45)
            except Exception as exc:
                future.cancel()
                yield {"success": False, "symbol": name, "message": type(exc).__name__}
    for name, future in pending:
        try:
            yield future.result(timeout=45)
        except Exception as exc:
            future.cancel()
            yield {"success": False, "symbol": name, "message": type(exc).__name__}


def quote_certificate(symbol, payload, *, now=None, max_age=30.):
    current = now or datetime.now(timezone.utc)
    snap = payload.get("snapshot") or payload
    provider = str(payload.get("source") or payload.get("provider") or snap.get("source") or "")
    received_raw = snap.get("received_at") or payload.get("received_at")
    exchange_raw = snap.get("exchange_timestamp") or payload.get("exchange_timestamp")
    reason = None
    received = _aware_timestamp(received_raw)
    exchange = _aware_timestamp(exchange_raw)
    price = snap.get("ltp", snap.get("mark"))
    try:
        price = float(price)
        if not math.isfinite(price) or price <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        price, reason = None, "INVALID_MARK"
    ages = [(current - ts).total_seconds() if ts else None for ts in (received, exchange)]
    if not payload.get("success"):
        reason = "MARKET_DATA_RATE_LIMITED" if str(payload.get("provider_code")) == "429" or payload.get("provider_state") == "RATE_LIMITED" else "DATA_UNAVAILABLE"
    elif not payload.get("symbol") or str(payload["symbol"]).upper() != str(symbol).upper():
        reason = "QUOTE_INSTRUMENT_MISMATCH"
    elif payload.get("stale") or payload.get("delayed") or payload.get("simulated") or "DELAYED" in str(payload.get("quality_flag")):
        reason = "DATA_NOT_LIVE"
    elif not (provider.startswith("FYERS") or provider in {"BINANCE_PUBLIC", "BINANCE"}):
        reason = "UNVERIFIED_PROVIDER"
    elif provider in {"BINANCE_PUBLIC", "BINANCE"} and str(symbol).upper() not in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
        reason = "PROVIDER_INSTRUMENT_MISMATCH"
    elif not received:
        reason = "MARK_RECEIVED_TIMESTAMP_MISSING"
    elif not exchange:
        reason = "MARK_EXCHANGE_TIMESTAMP_MISSING"
    elif any(a < -3 for a in ages):
        reason = "FUTURE_MARK_TIMESTAMP"
    elif any(a > max_age for a in ages):
        reason = "STALE_MARK"
    bid, ask = snap.get("bid"), snap.get("ask")
    spread_bps = None
    if bid is not None and ask is not None:
        try:
            bid, ask = float(bid), float(ask)
            if not math.isfinite(bid + ask) or not 0 < bid <= ask:
                raise ValueError()
            spread_bps = (ask - bid) / ((ask + bid) / 2) * 10000
        except (ValueError, TypeError):
            reason = "INVALID_BID_ASK"
    venue = "CRYPTO_24_7" if provider in {"BINANCE_PUBLIC", "BINANCE"} else "MCX" if str(symbol).startswith("MCX:") or symbol in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"} else "BSE" if str(symbol).startswith("BSE:") or symbol == "SENSEX" else "NSE"
    status = VENUE_SESSIONS.evaluate(venue, at=current).as_dict()
    session_open = bool(status.get("session_open", status.get("is_open", False)))
    # This terminal does not model India's closing auction. Since August 2026
    # some cash LTP fields may become indicative auction prices after 15:15.
    # Apply the conservative continuous-session boundary to all Indian cash/FO.
    local = current.astimezone(ZoneInfo("Asia/Kolkata"))
    continuous = not (venue in {"NSE", "BSE"} and (local.hour, local.minute) >= (15, 15))
    entry_window = not (venue in {"NSE", "BSE"} and (local.hour, local.minute) >= (15, 10))
    if reason is None and session_open and not continuous:
        reason = "CLOSING_AUCTION_NOT_MODELLED"
    result = {"success": price is not None, "symbol": symbol, "mark": price, "ltp": price,
              "provider": provider, "source": provider, "provider_symbol": payload.get("provider_symbol") or snap.get("provider_symbol"),
              "received_at": received_raw, "exchange_timestamp": exchange_raw,
              "age_seconds": max((a for a in ages if a is not None), default=None), "verified": reason is None,
              "stale": reason in {"STALE_MARK", "MARK_EXCHANGE_TIMESTAMP_MISSING", "FUTURE_MARK_TIMESTAMP"},
              "eligible_for_exit": reason is None and session_open and continuous,
              "eligible_for_entry": reason is None and session_open and continuous and entry_window,
              "session": status, "reason": reason or ("INTRADAY_ENTRY_CUTOFF" if session_open and not entry_window else None if session_open else "MARKET_SESSION_CLOSED"),
              "bid": bid, "ask": ask, "spread_bps": spread_bps,
              "provider_state": payload.get("provider_state"), "retry_after_seconds": payload.get("retry_after_seconds"),
              "paper_only": True, "live_execution": False}
    return result


def validate_candles(rows, timeframe_seconds, *, now=None):
    end = (now or datetime.now(timezone.utc)).timestamp()
    previous = None
    for row in rows:
        try:
            timestamp = float(row["time"])
            o, h, l, c = [float(row[k]) for k in ("open", "high", "low", "close")]
            if not all(math.isfinite(v) for v in (timestamp, o, h, l, c)) or min(o, h, l, c) <= 0:
                raise ValueError()
            if h < max(o, l, c) or l > min(o, h, c):
                return "INVALID_CANDLE_OHLC"
            if previous is not None and timestamp <= previous:
                return "OUT_OF_ORDER_OR_DUPLICATE_CANDLES"
            if timestamp > end + 3:
                return "FUTURE_CANDLE"
            previous = timestamp
        except (KeyError, ValueError, TypeError):
            return "INVALID_CANDLE"
    return None
