"""Unified read-only market data for autonomous paper trading.

FYERS supplies Indian indices and dynamically resolved MCX front-month futures.
Binance's market-data-only REST host supplies public crypto quotes and candles.
This module deliberately exposes no account, wallet, or order operation.
"""

from __future__ import annotations

import csv
from datetime import datetime, time as clock_time, timezone
import io
import json
import math
import re
import threading
import time
from typing import Any, Callable, Optional
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import pandas as pd

from agents.fyers_data_adapter import get_intraday_data, get_quote
from workstation.market_runtime import MARKET_RUNTIME, MarketRuntime
from workstation.trading_intelligence import analyze_market_asset


INDIA_TZ = ZoneInfo("Asia/Kolkata")
MCX_SYMBOL_MASTER = "https://public.fyers.in/sym_details/MCX_COM.csv"
CURRENCY_SYMBOL_MASTER = "https://public.fyers.in/sym_details/NSE_CD.csv"
BINANCE_MARKET_DATA = "https://data-api.binance.vision"

ASSET_UNIVERSE: dict[str, dict[str, str]] = {
    "NIFTY": {"label": "NIFTY 50", "asset_class": "INDEX", "provider": "FYERS", "currency": "INR"},
    "BANKNIFTY": {"label": "BANKNIFTY", "asset_class": "INDEX", "provider": "FYERS", "currency": "INR"},
    "SENSEX": {"label": "SENSEX", "asset_class": "INDEX", "provider": "FYERS", "currency": "INR"},
    "GOLD": {"label": "GOLD MINI", "asset_class": "COMMODITY", "provider": "FYERS", "currency": "INR", "root": "GOLDM"},
    "SILVER": {"label": "SILVER MINI", "asset_class": "COMMODITY", "provider": "FYERS", "currency": "INR", "root": "SILVERM"},
    "CRUDEOIL": {"label": "CRUDE OIL MINI", "asset_class": "COMMODITY", "provider": "FYERS", "currency": "INR", "root": "CRUDEOILM"},
    "NATURALGAS": {"label": "NATURAL GAS MINI", "asset_class": "COMMODITY", "provider": "FYERS", "currency": "INR", "root": "NATGASMINI"},
    "BTC": {"label": "BITCOIN", "asset_class": "CRYPTO", "provider": "BINANCE_PUBLIC", "currency": "USDT", "provider_symbol": "BTCUSDT"},
    "ETH": {"label": "ETHEREUM", "asset_class": "CRYPTO", "provider": "BINANCE_PUBLIC", "currency": "USDT", "provider_symbol": "ETHUSDT"},
    "SOL": {"label": "SOLANA", "asset_class": "CRYPTO", "provider": "BINANCE_PUBLIC", "currency": "USDT", "provider_symbol": "SOLUSDT"},
}

CRYPTO_INTERVALS = {"5m": "5m", "15m": "15m", "1h": "1h"}
MONTH_NUMBERS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
    "december": 12,
}
MCX_OPTION_ROOTS = {
    "CRUDEOIL": "CRUDEOIL",
    "GOLD": "GOLD",
    "SILVER": "SILVER",
    "NATURALGAS": "NATURALGAS",
}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


class UnifiedPaperMarketData:
    """Resolve, cache, and normalize data without any execution authority."""

    def __init__(
        self,
        *,
        market_runtime: MarketRuntime = MARKET_RUNTIME,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
        fyers_quote_loader: Callable[..., dict[str, Any]] = get_quote,
        fyers_history_loader: Callable[..., dict[str, Any]] = get_intraday_data,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.market_runtime = market_runtime
        self.urlopen = urlopen
        self.fyers_quote_loader = fyers_quote_loader
        self.fyers_history_loader = fyers_history_loader
        self.now = now
        self._lock = threading.RLock()
        self._quote_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._contract_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._master_cache: dict[str, tuple[float, str]] = {}
        self._resolved_contracts: dict[str, dict[str, Any]] = {}
        self._usd_inr_cache: tuple[float, float] = (0.0, 0.0)
        self._health: dict[str, dict[str, Any]] = {
            "FYERS": {"ready": False, "error": None},
            "BINANCE_PUBLIC": {"ready": True, "error": None},
        }

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(ASSET_UNIVERSE)

    def metadata(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper().replace(" ", "")
        if normalized not in ASSET_UNIVERSE:
            raise ValueError(f"Unsupported paper asset: {symbol}")
        return {"symbol": normalized, **ASSET_UNIVERSE[normalized]}

    def provider_symbol(self, symbol: str) -> dict[str, Any]:
        """Resolve a friendly asset to its current read-only market-data symbol."""

        meta = self.metadata(symbol)
        if meta["asset_class"] == "COMMODITY":
            contract = self._resolve_front_month(meta["root"])
            return {**meta, **contract}
        return {
            **meta,
            "provider_symbol": meta.get("provider_symbol") or meta["symbol"],
            "description": meta["label"],
        }

    def resolve_option_contract(
        self,
        underlying: str,
        strike: float,
        option_type: str,
        expiry_query: str,
    ) -> dict[str, Any]:
        """Resolve an exact active MCX option from FYERS' public symbol master."""

        normalized = str(underlying or "").strip().upper().replace(" ", "")
        root = MCX_OPTION_ROOTS.get(normalized)
        if not root:
            raise ValueError("Synthetic option resolution currently supports MCX commodities only.")
        kind = str(option_type or "").strip().upper()
        if kind not in {"CE", "PE"}:
            raise ValueError("Option type must be CALL/CE or PUT/PE.")
        requested_strike = _finite(strike)
        if requested_strike <= 0:
            raise ValueError("A positive option strike is required.")

        expiry_text = str(expiry_query or "").lower()
        requested_month = next(
            (number for name, number in MONTH_NUMBERS.items() if re.search(rf"\b{name}\b", expiry_text)),
            None,
        )
        year_match = re.search(r"\b(20\d{2})\b", expiry_text)
        requested_year = int(year_match.group(1)) if year_match else None
        now_epoch = self.now().timestamp()
        pattern = re.compile(
            rf"^{re.escape(root)}\s+(\d{{1,2}})\s+([A-Za-z]{{3}})\s+(\d{{2}})\s+"
            r"(\d+(?:\.\d+)?)\s+(CE|PE)$",
            flags=re.IGNORECASE,
        )
        candidates: list[dict[str, Any]] = []
        for row in csv.reader(io.StringIO(self._master(MCX_SYMBOL_MASTER))):
            if len(row) < 14 or row[13].strip().upper() != root:
                continue
            description = row[1].strip()
            match = pattern.match(description)
            if not match:
                continue
            _day, month_name, short_year, listed_strike, listed_kind = match.groups()
            expiry = _finite(row[8])
            provider_symbol = row[9].strip().upper()
            expiry_dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
            if expiry <= now_epoch or not provider_symbol or listed_kind.upper() != kind:
                continue
            if abs(float(listed_strike) - requested_strike) > 1e-9:
                continue
            if requested_month and expiry_dt.month != requested_month:
                continue
            full_year = 2000 + int(short_year)
            if requested_year and full_year != requested_year:
                continue
            candidates.append(
                {
                    "symbol": provider_symbol,
                    "provider_symbol": provider_symbol,
                    "description": description,
                    "label": description,
                    "underlying": normalized,
                    "root": root,
                    "strike": requested_strike,
                    "option_type": kind,
                    "expiry": expiry_dt.isoformat(),
                    "expiry_epoch": expiry,
                    "trading_hours": row[6].strip(),
                    "tick_size": _finite(row[4]),
                    "asset_class": "OPTION",
                    "provider": "FYERS",
                    "currency": "INR",
                }
            )
        if not candidates:
            month_label = f" for {expiry_query.strip()}" if str(expiry_query or "").strip() else ""
            raise RuntimeError(
                f"No active FYERS MCX {root} {requested_strike:g} {kind} contract was found{month_label}."
            )
        selected = min(candidates, key=lambda item: item["expiry_epoch"])
        with self._lock:
            self._resolved_contracts[selected["provider_symbol"]] = dict(selected)
        return dict(selected)

    def _read_url(self, url: str, *, max_bytes: int = 12_000_000) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "OMNI-JARVIS/1.0"})
        with self.urlopen(request, timeout=10) as response:
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError("Market-data response exceeded the safety limit.")
        return data

    def _json(self, path: str, parameters: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(parameters)
        raw = self._read_url(f"{BINANCE_MARKET_DATA}{path}?{query}", max_bytes=2_000_000)
        return json.loads(raw.decode("utf-8"))

    def _master(self, url: str) -> str:
        now = time.monotonic()
        with self._lock:
            cached = self._master_cache.get(url)
            if cached and now - cached[0] < 21_600:
                return cached[1]
        text = self._read_url(url).decode("utf-8-sig", errors="replace")
        with self._lock:
            self._master_cache[url] = (now, text)
        return text

    def _resolve_front_month(self, root: str, *, currency: bool = False) -> dict[str, Any]:
        key = f"{'CD' if currency else 'MCX'}:{root}"
        now_mono = time.monotonic()
        with self._lock:
            cached = self._contract_cache.get(key)
            if cached and now_mono - cached[0] < 21_600:
                return dict(cached[1])
        source = CURRENCY_SYMBOL_MASTER if currency else MCX_SYMBOL_MASTER
        cutoff = self.now().timestamp() + 86_400
        candidates: list[dict[str, Any]] = []
        for row in csv.reader(io.StringIO(self._master(source))):
            if len(row) < 14 or row[13].strip().upper() != root.upper():
                continue
            if not row[1].strip().upper().endswith(" FUT"):
                continue
            expiry = _finite(row[8])
            provider_symbol = row[9].strip()
            if expiry <= cutoff or not provider_symbol:
                continue
            candidates.append(
                {
                    "provider_symbol": provider_symbol,
                    "description": row[1].strip(),
                    "expiry": datetime.fromtimestamp(expiry, tz=timezone.utc).isoformat(),
                    "expiry_epoch": expiry,
                    "trading_hours": row[6].strip(),
                }
            )
        if not candidates:
            raise RuntimeError(f"No valid front-month contract was found for {root}.")
        selected = min(candidates, key=lambda item: item["expiry_epoch"])
        with self._lock:
            self._contract_cache[key] = (now_mono, selected)
        return dict(selected)

    def session_open(self, symbol: str) -> bool:
        meta = self.metadata(symbol)
        if meta["asset_class"] == "CRYPTO":
            return True
        now = self.now().astimezone(INDIA_TZ)
        if now.weekday() >= 5:
            return False
        current = now.time().replace(tzinfo=None)
        if meta["asset_class"] == "INDEX":
            return clock_time(9, 15) <= current <= clock_time(15, 30)
        return clock_time(9, 0) <= current <= clock_time(23, 30)

    def _usd_inr(self) -> float:
        now_mono = time.monotonic()
        with self._lock:
            cached_at, cached_value = self._usd_inr_cache
            if cached_value > 0 and now_mono - cached_at < 3_600:
                return cached_value
        contract = self._resolve_front_month("USDINR", currency=True)
        quote = self.fyers_quote_loader(contract["provider_symbol"])
        rate = _finite(quote.get("ltp")) if quote.get("success") else 0.0
        if rate <= 0:
            raise RuntimeError("FYERS USDINR reference is unavailable for crypto valuation.")
        with self._lock:
            self._usd_inr_cache = (now_mono, rate)
        return rate

    def quote(self, symbol: str, *, use_cache: bool = True) -> dict[str, Any]:
        requested = str(symbol or "").strip().upper().replace(" ", "")
        if re.fullmatch(r"MCX:[A-Z0-9_-]+(?:CE|PE)", requested):
            contract = dict(
                self._resolved_contracts.get(
                    requested,
                    {
                        "symbol": requested,
                        "provider_symbol": requested,
                        "description": requested,
                        "label": requested,
                        "asset_class": "OPTION",
                        "provider": "FYERS",
                        "currency": "INR",
                    },
                )
            )
            now_mono = time.monotonic()
            with self._lock:
                cached = self._quote_cache.get(requested)
                if use_cache and cached and now_mono - cached[0] < 10:
                    return dict(cached[1])
            try:
                payload = self.fyers_quote_loader(requested)
                native_ltp = _finite(payload.get("ltp"))
                if not payload.get("success") or native_ltp <= 0:
                    raise RuntimeError(str(payload.get("message") or "FYERS option quote is unavailable."))
                result = {
                    **payload,
                    **contract,
                    "success": True,
                    "symbol": requested,
                    "provider_symbol": requested,
                    "native_ltp": native_ltp,
                    "valuation_ltp": native_ltp,
                    "valuation_currency": "INR",
                    "session_open": self.session_open("CRUDEOIL"),
                    "received_at": self.now().isoformat(),
                }
                with self._lock:
                    self._quote_cache[requested] = (now_mono, result)
                    self._health["FYERS"] = {"ready": True, "error": None}
                return dict(result)
            except Exception as error:
                with self._lock:
                    self._health["FYERS"] = {"ready": False, "error": str(error)[:240]}
                return {
                    **contract,
                    "success": False,
                    "session_open": self.session_open("CRUDEOIL"),
                    "message": str(error)[:240],
                }
        meta = self.metadata(symbol)
        normalized = meta["symbol"]
        now_mono = time.monotonic()
        with self._lock:
            cached = self._quote_cache.get(normalized)
            if use_cache and cached and now_mono - cached[0] < 10:
                return dict(cached[1])
        try:
            if meta["asset_class"] == "INDEX":
                snapshot = self.market_runtime.snapshot(normalized)
                if not snapshot or _finite(snapshot.get("ltp")) <= 0:
                    raise RuntimeError("Live FYERS index quote is unavailable.")
                payload = {**snapshot, "source": "FYERS", "provider_symbol": snapshot.get("provider_symbol") or normalized}
            elif meta["asset_class"] == "COMMODITY":
                contract = self._resolve_front_month(meta["root"])
                payload = self.fyers_quote_loader(contract["provider_symbol"])
                if not payload.get("success") or _finite(payload.get("ltp")) <= 0:
                    raise RuntimeError(str(payload.get("message") or "FYERS commodity quote is unavailable."))
                payload = {**payload, **contract, "source": "FYERS"}
            else:
                raw = self._json("/api/v3/ticker/24hr", {"symbol": meta["provider_symbol"]})
                payload = {
                    "success": True,
                    "source": "BINANCE_PUBLIC",
                    "provider_symbol": meta["provider_symbol"],
                    "ltp": _finite(raw.get("lastPrice")),
                    "change": _finite(raw.get("priceChange")),
                    "change_percent": _finite(raw.get("priceChangePercent")),
                    "high": _finite(raw.get("highPrice")),
                    "low": _finite(raw.get("lowPrice")),
                    "volume": _finite(raw.get("volume")),
                    "exchange_timestamp": raw.get("closeTime"),
                }
                if payload["ltp"] <= 0:
                    raise RuntimeError("Public crypto quote did not contain a valid price.")
            native_ltp = _finite(payload.get("ltp"))
            valuation_ltp = native_ltp * self._usd_inr() if meta["asset_class"] == "CRYPTO" else native_ltp
            result = {
                **payload,
                **meta,
                "success": True,
                "native_ltp": native_ltp,
                "valuation_ltp": valuation_ltp,
                "valuation_currency": "INR",
                "session_open": self.session_open(normalized),
                "received_at": self.now().isoformat(),
            }
            with self._lock:
                self._quote_cache[normalized] = (now_mono, result)
                self._health[meta["provider"]] = {"ready": True, "error": None}
            return dict(result)
        except Exception as error:
            with self._lock:
                self._health[meta["provider"]] = {"ready": False, "error": str(error)[:240]}
            return {**meta, "success": False, "session_open": self.session_open(normalized), "message": str(error)[:240]}

    def history(self, symbol: str, *, timeframe: str, bars: int) -> dict[str, Any]:
        meta = self.metadata(symbol)
        try:
            if meta["asset_class"] == "INDEX":
                return self.fyers_history_loader(meta["symbol"], timeframe=timeframe, bars=bars)
            if meta["asset_class"] == "COMMODITY":
                contract = self._resolve_front_month(meta["root"])
                result = self.fyers_history_loader(contract["provider_symbol"], timeframe=timeframe, bars=bars)
                return {**result, "symbol": meta["symbol"], "provider_symbol": contract["provider_symbol"], "asset_class": "COMMODITY"}
            interval = CRYPTO_INTERVALS.get(str(timeframe).lower())
            if not interval:
                raise ValueError(f"Unsupported crypto timeframe: {timeframe}")
            rows = self._json(
                "/api/v3/klines",
                {"symbol": meta["provider_symbol"], "interval": interval, "limit": min(max(int(bars), 60), 1000)},
            )
            normalized_rows = [row[:6] for row in rows if isinstance(row, list) and len(row) >= 6]
            frame = pd.DataFrame(normalized_rows, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
            frame["Timestamp"] = pd.to_datetime(frame["Timestamp"], unit="ms", utc=True, errors="coerce")
            for column in ("Open", "High", "Low", "Close", "Volume"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame = frame.dropna().drop_duplicates(subset=["Timestamp"]).sort_values("Timestamp").set_index("Timestamp").tail(bars)
            if len(frame) < 60:
                raise RuntimeError("Public crypto history returned too few complete candles.")
            return {
                "success": True,
                "source": "BINANCE_PUBLIC",
                "data_quality": "PUBLIC_SPOT_OHLCV",
                "symbol": meta["symbol"],
                "provider_symbol": meta["provider_symbol"],
                "timeframe": timeframe,
                "bars": len(frame),
                "data": frame,
                "timestamp": self.now().isoformat(),
            }
        except Exception as error:
            return {"success": False, "source": meta["provider"], "symbol": meta["symbol"], "timeframe": timeframe, "bars": 0, "data": None, "message": str(error)[:240]}

    def analyze(self, symbol: str) -> dict[str, Any]:
        return analyze_market_asset(
            symbol,
            loader=self.history,
            provider_label=self.metadata(symbol)["provider"],
        )

    def status(self) -> dict[str, Any]:
        fyers = self.market_runtime.status()
        with self._lock:
            health = {key: dict(value) for key, value in self._health.items()}
        health["FYERS"]["ready"] = bool(fyers.get("connected") or fyers.get("configured"))
        health["FYERS"]["error"] = fyers.get("error")
        return {
            "paper_only": True,
            "live_orders": False,
            "providers": health,
            "symbols": self.symbols,
            "asset_classes": ["INDEX", "COMMODITY", "CRYPTO"],
        }

    def public_universe(self, *, resolve_contracts: bool = False) -> list[dict[str, Any]]:
        result = []
        for symbol, metadata in ASSET_UNIVERSE.items():
            item = {"symbol": symbol, **metadata, "session_open": self.session_open(symbol)}
            if resolve_contracts and metadata["asset_class"] == "COMMODITY":
                try:
                    item.update(self._resolve_front_month(metadata["root"]))
                except Exception as error:
                    item["error"] = str(error)[:160]
            result.append(item)
        return result


PAPER_MARKET_DATA = UnifiedPaperMarketData()
