"""Unified read-only market data for autonomous paper trading.

FYERS supplies Indian indices and dynamically resolved MCX front-month futures.
Binance's market-data-only REST host supplies public crypto quotes and candles.
This module deliberately exposes no account, wallet, or order operation.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
import os
import re
import threading
import time
from typing import Any, Callable, Optional
import urllib.parse
import urllib.request

import pandas as pd

from agents.fyers_data_adapter import get_intraday_data, get_quote
from workstation.market_data_contract import (
    VENUE_SESSIONS,
    MarketEventType,
    canonical_market_event,
    canonical_market_datum,
)
from workstation.market_runtime import MARKET_RUNTIME, MarketRuntime
from workstation.trading_intelligence import analyze_market_asset


MCX_SYMBOL_MASTER = "https://public.fyers.in/sym_details/MCX_COM.csv"
CURRENCY_SYMBOL_MASTER = "https://public.fyers.in/sym_details/NSE_CD.csv"
BINANCE_MARKET_DATA = "https://data-api.binance.vision"
PUBLIC_FX_API = "https://api.frankfurter.dev/v1/latest"

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
    "BNB": {"label": "BNB", "asset_class": "CRYPTO", "provider": "BINANCE_PUBLIC", "currency": "USDT", "provider_symbol": "BNBUSDT"},
    "XRP": {"label": "XRP", "asset_class": "CRYPTO", "provider": "BINANCE_PUBLIC", "currency": "USDT", "provider_symbol": "XRPUSDT"},
}

CRYPTO_INTERVALS = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1d",
}
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
        self._instrument_spec_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._master_cache: dict[str, tuple[float, str]] = {}
        self._resolved_contracts: dict[str, dict[str, Any]] = {}
        self._usd_inr_cache: tuple[float, float] = (0.0, 0.0)
        self._health: dict[str, dict[str, Any]] = {
            "FYERS": {"ready": False, "error": None},
            "BINANCE_PUBLIC": {"ready": True, "error": None},
            "PUBLIC_FX": {"ready": False, "error": None},
        }

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(ASSET_UNIVERSE)

    def metadata(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper().replace(" ", "")
        if normalized in ASSET_UNIVERSE:
            return {"symbol": normalized, **ASSET_UNIVERSE[normalized]}
        from workstation.equity_universe import resolve_equity_symbol

        equity = resolve_equity_symbol(symbol)
        if equity is None:
            raise ValueError(f"Unsupported paper asset: {symbol}")
        return {
            "symbol": equity.symbol,
            "label": equity.label,
            "asset_class": "EQUITY",
            "provider": equity.provider,
            "currency": equity.currency,
            "provider_symbol": equity.provider_symbol,
            "exchange": equity.exchange,
            "market": equity.market,
            "auto_execution_eligible": equity.market == "INDIA",
        }

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
                    "lot_size": _finite(row[3]),
                    "contract_multiplier": _finite(row[3]),
                    "quantity_step": 1.0,
                    "instrument_type": "OPTION",
                    "spec_source": "FYERS_PUBLIC_SYMBOL_MASTER",
                    "spec_verified": _finite(row[3]) > 0 and _finite(row[4]) > 0,
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
                    "tick_size": _finite(row[4]),
                    "lot_size": _finite(row[3]),
                    "contract_multiplier": _finite(row[3]),
                    "quantity_step": 1.0,
                    "instrument_type": "FUTURE",
                    "spec_source": "FYERS_PUBLIC_SYMBOL_MASTER",
                    "spec_verified": _finite(row[3]) > 0 and _finite(row[4]) > 0,
                }
            )
        if not candidates:
            raise RuntimeError(f"No valid front-month contract was found for {root}.")
        selected = min(candidates, key=lambda item: item["expiry_epoch"])
        with self._lock:
            self._contract_cache[key] = (now_mono, selected)
        return dict(selected)

    def instrument_spec(self, symbol: str) -> dict[str, Any]:
        """Return a read-only, provider-derived Paper Desk accounting certificate."""

        requested = str(symbol or "").strip().upper().replace(" ", "")
        if re.fullmatch(r"MCX:[A-Z0-9_-]+(?:CE|PE)", requested):
            resolved = dict(self._resolved_contracts.get(requested) or {})
            verified = bool(resolved.get("spec_verified"))
            return {
                "symbol": requested,
                "provider_symbol": requested,
                "asset_class": "OPTION",
                "instrument_type": "OPTION",
                "native_currency": "INR",
                "valuation_currency": "INR",
                "quantity_step": _finite(resolved.get("quantity_step"), 1.0),
                "contract_multiplier": _finite(resolved.get("contract_multiplier")),
                "tick_size": _finite(resolved.get("tick_size")),
                "source": resolved.get("spec_source") or "FYERS_PUBLIC_SYMBOL_MASTER",
                "verified": verified,
                "verification_reason": "FYERS_SYMBOL_MASTER" if verified else "OPTION_CONTRACT_NOT_RESOLVED",
                "cost_model_status": "UNCONFIGURED",
            }

        meta = self.metadata(symbol)
        if meta["asset_class"] == "COMMODITY":
            contract = self._resolve_front_month(meta["root"])
            verified = bool(contract.get("spec_verified"))
            return {
                "symbol": meta["symbol"],
                "provider_symbol": contract["provider_symbol"],
                "asset_class": "COMMODITY",
                "instrument_type": "FUTURE",
                "native_currency": "INR",
                "valuation_currency": "INR",
                "quantity_step": _finite(contract.get("quantity_step"), 1.0),
                "contract_multiplier": _finite(contract.get("contract_multiplier")),
                "tick_size": _finite(contract.get("tick_size")),
                "source": contract.get("spec_source") or "FYERS_PUBLIC_SYMBOL_MASTER",
                "verified": verified,
                "verification_reason": "FYERS_SYMBOL_MASTER" if verified else "CONTRACT_SPEC_INCOMPLETE",
                "cost_model_status": "UNCONFIGURED",
            }

        if meta["asset_class"] == "CRYPTO":
            provider_symbol = meta["provider_symbol"]
            cache_key = f"BINANCE:{provider_symbol}"
            now_mono = time.monotonic()
            with self._lock:
                cached = self._instrument_spec_cache.get(cache_key)
                if cached and now_mono - cached[0] < 21_600:
                    return dict(cached[1])
            payload = self._json("/api/v3/exchangeInfo", {"symbol": provider_symbol})
            symbols = payload.get("symbols") if isinstance(payload, dict) else None
            row = symbols[0] if isinstance(symbols, list) and symbols else {}
            filters = {
                str(item.get("filterType")): item
                for item in (row.get("filters") or [])
                if isinstance(item, dict)
            }
            tick_size = _finite((filters.get("PRICE_FILTER") or {}).get("tickSize"))
            quantity_step = _finite((filters.get("LOT_SIZE") or {}).get("stepSize"))
            verified = bool(row.get("symbol") == provider_symbol and tick_size > 0 and quantity_step > 0)
            result = {
                "symbol": meta["symbol"],
                "provider_symbol": provider_symbol,
                "asset_class": "CRYPTO",
                "instrument_type": "SPOT",
                "native_currency": "USDT",
                "valuation_currency": "INR",
                "quantity_step": quantity_step,
                "contract_multiplier": 1.0,
                "tick_size": tick_size,
                "source": "BINANCE_PUBLIC_EXCHANGE_INFO",
                "verified": verified,
                "verification_reason": "BINANCE_EXCHANGE_INFO" if verified else "EXCHANGE_FILTERS_INCOMPLETE",
                "cost_model_status": "UNCONFIGURED",
            }
            with self._lock:
                self._instrument_spec_cache[cache_key] = (now_mono, result)
            return dict(result)

        # Cash equities and index reference units do not represent a leveraged
        # derivative contract.  They remain explicitly synthetic paper units.
        instrument_type = "SYNTHETIC_INDEX" if meta["asset_class"] == "INDEX" else "SPOT"
        return {
            "symbol": meta["symbol"],
            "provider_symbol": meta.get("provider_symbol") or meta["symbol"],
            "asset_class": meta["asset_class"],
            "instrument_type": instrument_type,
            "native_currency": meta["currency"],
            "valuation_currency": "INR",
            "quantity_step": 1.0,
            "contract_multiplier": 1.0,
            "tick_size": None,
            "source": "SYNTHETIC_REFERENCE_UNIT" if meta["asset_class"] == "INDEX" else "VERIFIED_CASH_SYMBOL",
            "verified": True,
            "verification_reason": "NON_DERIVATIVE_PAPER_UNIT",
            "cost_model_status": "UNCONFIGURED",
        }

    def session_open(self, symbol: str) -> bool:
        meta = self.metadata(symbol)
        venue = VENUE_SESSIONS.venue_for(meta)
        return VENUE_SESSIONS.evaluate(venue, at=self.now()).session_open

    def session_status(self, symbol: str) -> dict[str, Any]:
        meta = self.metadata(symbol)
        venue = VENUE_SESSIONS.venue_for(meta)
        return VENUE_SESSIONS.evaluate(venue, at=self.now()).as_dict()

    def _normalize_history_result(
        self,
        result: dict[str, Any],
        *,
        metadata: dict[str, Any],
        timeframe: str,
    ) -> dict[str, Any]:
        normalized = dict(result)
        normalized.setdefault("source", metadata["provider"])
        normalized.setdefault("provider_symbol", metadata.get("provider_symbol") or metadata["symbol"])
        normalized.setdefault("symbol", metadata["symbol"])
        normalized.setdefault("timeframe", timeframe)
        frame = normalized.get("data")
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            normalized["exchange_timestamp"] = frame.index[-1]
        received_at = self.now()
        timeframe_seconds = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1_800,
            "1h": 3_600, "2h": 7_200, "4h": 14_400, "1d": 86_400,
        }.get(str(timeframe).lower(), 300)
        normalized.update(
            canonical_market_datum(
                normalized,
                event_type=MarketEventType.BAR,
                timeframe=timeframe,
                received_at=received_at,
                stale_after_seconds=max(90, timeframe_seconds * 3),
            ).as_dict()
        )
        if isinstance(frame, pd.DataFrame) and not frame.empty and normalized.get("verified"):
            last = frame.iloc[-1]
            normalized["event_bus"] = self._publish_event(
                normalized,
                MarketEventType.BAR,
                {
                    "open": float(last.get("Open", last.get("open"))),
                    "high": float(last.get("High", last.get("high"))),
                    "low": float(last.get("Low", last.get("low"))),
                    "close": float(last.get("Close", last.get("close"))),
                    "volume": float(last.get("Volume", last.get("volume", 0.0))),
                },
                timeframe=timeframe,
            )
        return normalized

    @staticmethod
    def _publish_event(
        source: dict[str, Any],
        event_type: MarketEventType,
        payload: dict[str, Any],
        *,
        timeframe: str = "tick",
    ) -> dict[str, Any]:
        try:
            from workstation.market_event_bus import MARKET_EVENT_BUS

            return MARKET_EVENT_BUS.publish(
                canonical_market_event(
                    source,
                    payload,
                    event_type=event_type,
                    timeframe=timeframe,
                    stale_after_seconds=90 if timeframe == "tick" else 300,
                )
            )
        except (TypeError, ValueError) as error:
            return {
                "accepted": False,
                "reason": type(error).__name__,
                "paper_only": True,
                "live_execution": False,
            }

    def _usd_inr(self) -> float:
        now_mono = time.monotonic()
        with self._lock:
            cached_at, cached_value = self._usd_inr_cache
            if cached_value > 0 and now_mono - cached_at < 3_600:
                return cached_value
        errors: list[str] = []
        try:
            contract = self._resolve_front_month("USDINR", currency=True)
            quote = self.fyers_quote_loader(contract["provider_symbol"])
            rate = _finite(quote.get("ltp")) if quote.get("success") else 0.0
            if rate <= 0:
                raise RuntimeError(str(quote.get("message") or "invalid FYERS USDINR quote"))
            with self._lock:
                self._health["FYERS"] = {"ready": True, "error": None}
        except Exception as error:
            errors.append(f"FYERS: {error}")
            rate = 0.0

        if rate <= 0:
            try:
                query = urllib.parse.urlencode({"base": "USD", "symbols": "INR"})
                request = urllib.request.Request(
                    f"{PUBLIC_FX_API}?{query}",
                    headers={"User-Agent": "JARVIS-Paper-Valuation/5.5"},
                )
                with self.urlopen(request, timeout=8) as response:
                    payload = json.loads(response.read(100_000).decode("utf-8"))
                rate = _finite((payload.get("rates") or {}).get("INR"))
                if rate <= 0:
                    raise RuntimeError("public USDINR response did not include a valid rate")
                with self._lock:
                    self._health["PUBLIC_FX"] = {
                        "ready": True,
                        "error": None,
                        "source": "FRANKFURTER_CENTRAL_BANK_REFERENCE",
                        "as_of": payload.get("date"),
                    }
            except Exception as error:
                errors.append(f"PUBLIC_FX: {error}")
                with self._lock:
                    self._health["PUBLIC_FX"] = {"ready": False, "error": str(error)[:240]}
                rate = 0.0

        if rate <= 0:
            raise RuntimeError("USDINR valuation unavailable; " + "; ".join(errors)[:500])
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
                received_at = self.now()
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
                    "received_at": received_at.isoformat(),
                }
                result.update(canonical_market_datum(result, received_at=received_at).as_dict())
                result["event_bus"] = self._publish_event(
                    result, MarketEventType.QUOTE_TICK, {"ltp": native_ltp}
                )
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
            elif meta["asset_class"] == "EQUITY":
                if meta.get("market") == "INDIA":
                    payload = self.fyers_quote_loader(meta["provider_symbol"])
                    if not payload.get("success") or _finite(payload.get("ltp")) <= 0:
                        raise RuntimeError(str(payload.get("message") or "FYERS equity quote is unavailable."))
                    payload = {**payload, "source": "FYERS"}
                else:
                    from workstation.global_equity_data import global_equity_quote

                    global_payload = global_equity_quote(meta["provider_symbol"])
                    snapshot = global_payload.get("snapshot") or {}
                    if not global_payload.get("success") or _finite(snapshot.get("ltp")) <= 0:
                        raise RuntimeError(str(global_payload.get("message") or "Global equity quote is unavailable."))
                    payload = {**snapshot, "success": True, "source": global_payload.get("source")}
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
            received_at = self.now()
            result = {
                **payload,
                **meta,
                "success": True,
                "native_ltp": native_ltp,
                "valuation_ltp": valuation_ltp,
                "valuation_currency": "INR",
                "session_open": self.session_open(normalized),
                "received_at": received_at.isoformat(),
            }
            result.update(canonical_market_datum(result, received_at=received_at).as_dict())
            result["event_bus"] = self._publish_event(
                result,
                MarketEventType.QUOTE_TICK,
                {
                    "ltp": native_ltp,
                    "change": _finite(payload.get("change")),
                    "change_percent": _finite(payload.get("change_percent")),
                },
            )
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
                result = self.fyers_history_loader(meta["symbol"], timeframe=timeframe, bars=bars)
                return self._normalize_history_result(result, metadata=meta, timeframe=timeframe)
            if meta["asset_class"] == "COMMODITY":
                contract = self._resolve_front_month(meta["root"])
                result = self.fyers_history_loader(contract["provider_symbol"], timeframe=timeframe, bars=bars)
                return self._normalize_history_result(
                    {**result, "symbol": meta["symbol"], "provider_symbol": contract["provider_symbol"], "asset_class": "COMMODITY"},
                    metadata=meta,
                    timeframe=timeframe,
                )
            if meta["asset_class"] == "EQUITY":
                if meta.get("market") == "INDIA":
                    result = self.fyers_history_loader(
                        meta["provider_symbol"], timeframe=timeframe, bars=bars
                    )
                    return self._normalize_history_result({
                        **result,
                        "symbol": meta["symbol"],
                        "provider_symbol": meta["provider_symbol"],
                        "asset_class": "EQUITY",
                    }, metadata=meta, timeframe=timeframe)
                from workstation.global_equity_data import global_equity_candles

                result = global_equity_candles(meta["provider_symbol"], timeframe, bars)
                if not result.get("success"):
                    raise RuntimeError(str(result.get("message") or "Global equity history unavailable."))
                frame = pd.DataFrame(result["candles"])
                frame["Timestamp"] = pd.to_datetime(frame["time"], unit="s", utc=True)
                frame = frame.rename(
                    columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
                ).set_index("Timestamp")
                return self._normalize_history_result(
                    {**result, "data": frame, "asset_class": "EQUITY"},
                    metadata=meta,
                    timeframe=timeframe,
                )
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
            return self._normalize_history_result({
                "success": True,
                "source": "BINANCE_PUBLIC",
                "data_quality": "PUBLIC_SPOT_OHLCV",
                "symbol": meta["symbol"],
                "provider_symbol": meta["provider_symbol"],
                "timeframe": timeframe,
                "bars": len(frame),
                "data": frame,
                "timestamp": self.now().isoformat(),
            }, metadata=meta, timeframe=timeframe)
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
            "asset_classes": ["INDEX", "EQUITY", "COMMODITY", "CRYPTO"],
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
