from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import io
import re
import threading
import time
from typing import Any, Callable
import urllib.request


NIFTY50_CONSTITUENTS_URL = (
    "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"
)

# Official NSE snapshot retrieved 2026-08-25. Runtime refreshes the official
# CSV and uses this only when the exchange download is unavailable.
NIFTY50_FALLBACK: tuple[tuple[str, str, str], ...] = (
    ("ADANIENT", "Adani Enterprises Ltd.", "Metals & Mining"),
    ("ADANIPORTS", "Adani Ports and Special Economic Zone Ltd.", "Services"),
    ("APOLLOHOSP", "Apollo Hospitals Enterprise Ltd.", "Healthcare"),
    ("ASIANPAINT", "Asian Paints Ltd.", "Consumer Durables"),
    ("AXISBANK", "Axis Bank Ltd.", "Financial Services"),
    ("BAJAJ-AUTO", "Bajaj Auto Ltd.", "Automobile and Auto Components"),
    ("BAJFINANCE", "Bajaj Finance Ltd.", "Financial Services"),
    ("BAJAJFINSV", "Bajaj Finserv Ltd.", "Financial Services"),
    ("BEL", "Bharat Electronics Ltd.", "Capital Goods"),
    ("BHARTIARTL", "Bharti Airtel Ltd.", "Telecommunication"),
    ("CIPLA", "Cipla Ltd.", "Healthcare"),
    ("COALINDIA", "Coal India Ltd.", "Oil Gas & Consumable Fuels"),
    ("DRREDDY", "Dr. Reddy's Laboratories Ltd.", "Healthcare"),
    ("EICHERMOT", "Eicher Motors Ltd.", "Automobile and Auto Components"),
    ("ETERNAL", "Eternal Ltd.", "Consumer Services"),
    ("GRASIM", "Grasim Industries Ltd.", "Construction Materials"),
    ("HCLTECH", "HCL Technologies Ltd.", "Information Technology"),
    ("HDFCBANK", "HDFC Bank Ltd.", "Financial Services"),
    ("HDFCLIFE", "HDFC Life Insurance Company Ltd.", "Financial Services"),
    ("HINDALCO", "Hindalco Industries Ltd.", "Metals & Mining"),
    ("HINDUNILVR", "Hindustan Unilever Ltd.", "Fast Moving Consumer Goods"),
    ("ICICIBANK", "ICICI Bank Ltd.", "Financial Services"),
    ("ITC", "ITC Ltd.", "Fast Moving Consumer Goods"),
    ("INFY", "Infosys Ltd.", "Information Technology"),
    ("INDIGO", "InterGlobe Aviation Ltd.", "Services"),
    ("JSWSTEEL", "JSW Steel Ltd.", "Metals & Mining"),
    ("JIOFIN", "Jio Financial Services Ltd.", "Financial Services"),
    ("KOTAKBANK", "Kotak Mahindra Bank Ltd.", "Financial Services"),
    ("LT", "Larsen & Toubro Ltd.", "Construction"),
    ("M&M", "Mahindra & Mahindra Ltd.", "Automobile and Auto Components"),
    ("MARUTI", "Maruti Suzuki India Ltd.", "Automobile and Auto Components"),
    ("MAXHEALTH", "Max Healthcare Institute Ltd.", "Healthcare"),
    ("NTPC", "NTPC Ltd.", "Power"),
    ("NESTLEIND", "Nestle India Ltd.", "Fast Moving Consumer Goods"),
    ("ONGC", "Oil & Natural Gas Corporation Ltd.", "Oil Gas & Consumable Fuels"),
    ("POWERGRID", "Power Grid Corporation of India Ltd.", "Power"),
    ("RELIANCE", "Reliance Industries Ltd.", "Oil Gas & Consumable Fuels"),
    ("SBILIFE", "SBI Life Insurance Company Ltd.", "Financial Services"),
    ("SHRIRAMFIN", "Shriram Finance Ltd.", "Financial Services"),
    ("SBIN", "State Bank of India", "Financial Services"),
    ("SUNPHARMA", "Sun Pharmaceutical Industries Ltd.", "Healthcare"),
    ("TCS", "Tata Consultancy Services Ltd.", "Information Technology"),
    ("TATACONSUM", "Tata Consumer Products Ltd.", "Fast Moving Consumer Goods"),
    ("TMPV", "Tata Motors Passenger Vehicles Ltd.", "Automobile and Auto Components"),
    ("TATASTEEL", "Tata Steel Ltd.", "Metals & Mining"),
    ("TECHM", "Tech Mahindra Ltd.", "Information Technology"),
    ("TITAN", "Titan Company Ltd.", "Consumer Durables"),
    ("TRENT", "Trent Ltd.", "Consumer Services"),
    ("ULTRACEMCO", "UltraTech Cement Ltd.", "Construction Materials"),
    ("WIPRO", "Wipro Ltd.", "Information Technology"),
)

GLOBAL_ALIASES: dict[str, tuple[str, str, str]] = {
    "APPLE": ("AAPL", "Apple Inc.", "NASDAQ"),
    "AAPL": ("AAPL", "Apple Inc.", "NASDAQ"),
    "MICROSOFT": ("MSFT", "Microsoft Corporation", "NASDAQ"),
    "MSFT": ("MSFT", "Microsoft Corporation", "NASDAQ"),
    "ALPHABET": ("GOOGL", "Alphabet Inc.", "NASDAQ"),
    "GOOGLE": ("GOOGL", "Alphabet Inc.", "NASDAQ"),
    "GOOGL": ("GOOGL", "Alphabet Inc.", "NASDAQ"),
    "AMAZON": ("AMZN", "Amazon.com Inc.", "NASDAQ"),
    "AMZN": ("AMZN", "Amazon.com Inc.", "NASDAQ"),
    "NVIDIA": ("NVDA", "NVIDIA Corporation", "NASDAQ"),
    "NVDA": ("NVDA", "NVIDIA Corporation", "NASDAQ"),
    "META": ("META", "Meta Platforms Inc.", "NASDAQ"),
    "TESLA": ("TSLA", "Tesla Inc.", "NASDAQ"),
    "TSLA": ("TSLA", "Tesla Inc.", "NASDAQ"),
}

INDIA_NAME_ALIASES = {
    "RELIANCE INDUSTRIES": "RELIANCE",
    "RELIANCE": "RELIANCE",
    "STATE BANK OF INDIA": "SBIN",
    "SBI": "SBIN",
    "TATA CONSULTANCY SERVICES": "TCS",
    "LARSEN AND TOUBRO": "LT",
    "LARSEN & TOUBRO": "LT",
}


@dataclass(frozen=True)
class EquityInstrument:
    symbol: str
    label: str
    market: str
    exchange: str
    provider: str
    provider_symbol: str
    currency: str
    industry: str = ""
    constituent_of: str | None = None
    data_quality: str = ""

    @property
    def kind(self) -> str:
        return "INDIA_EQUITY" if self.market == "INDIA" else "GLOBAL_EQUITY"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "kind": self.kind, "asset_class": "EQUITY"}


_CACHE_LOCK = threading.RLock()
_CACHE: tuple[float, list[EquityInstrument], str] | None = None
_DYNAMIC: dict[str, EquityInstrument] = {}


def _remember(instrument: EquityInstrument) -> EquityInstrument:
    with _CACHE_LOCK:
        _DYNAMIC[instrument.symbol] = instrument
    return instrument


def _fallback_constituents() -> list[EquityInstrument]:
    return [
        EquityInstrument(
            symbol=symbol,
            label=label,
            market="INDIA",
            exchange="NSE",
            provider="FYERS",
            provider_symbol=f"NSE:{symbol}-EQ",
            currency="INR",
            industry=industry,
            constituent_of="NIFTY50",
            data_quality="OFFICIAL_NSE_FALLBACK_2026_08_25",
        )
        for symbol, label, industry in NIFTY50_FALLBACK
    ]


def _download_text(url: str, *, timeout: float = 8.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Quant-Research/5.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(1_000_000).decode("utf-8-sig", errors="replace")


def nifty50_constituents(
    *,
    force_refresh: bool = False,
    loader: Callable[[str], str] | None = None,
) -> tuple[list[EquityInstrument], str]:
    global _CACHE
    now = time.monotonic()
    with _CACHE_LOCK:
        if _CACHE and not force_refresh and now - _CACHE[0] < 21_600:
            return list(_CACHE[1]), _CACHE[2]

    source = "OFFICIAL_NSE_RUNTIME"
    try:
        text = (loader or _download_text)(NIFTY50_CONSTITUENTS_URL)
        rows = list(csv.DictReader(io.StringIO(text)))
        instruments = []
        for row in rows:
            symbol = str(row.get("Symbol") or "").strip().upper()
            label = str(row.get("Company Name") or symbol).strip()
            series = str(row.get("Series") or "EQ").strip().upper()
            if not symbol or series != "EQ":
                continue
            instruments.append(
                EquityInstrument(
                    symbol=symbol,
                    label=label,
                    market="INDIA",
                    exchange="NSE",
                    provider="FYERS",
                    provider_symbol=f"NSE:{symbol}-EQ",
                    currency="INR",
                    industry=str(row.get("Industry") or "").strip(),
                    constituent_of="NIFTY50",
                    data_quality="OFFICIAL_NSE_RUNTIME",
                )
            )
        if len(instruments) != 50:
            raise RuntimeError(f"Official NIFTY 50 file returned {len(instruments)} constituents.")
    except Exception:
        instruments = _fallback_constituents()
        source = "OFFICIAL_NSE_FALLBACK_2026_08_25"

    with _CACHE_LOCK:
        _CACHE = (now, list(instruments), source)
    return instruments, source


def _nifty_index() -> dict[str, EquityInstrument]:
    rows, _source = nifty50_constituents()
    return {row.symbol: row for row in rows}


def resolve_equity_symbol(value: str) -> EquityInstrument | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    upper = raw.upper().strip()

    with _CACHE_LOCK:
        remembered = _DYNAMIC.get(upper)
    if remembered is not None:
        return remembered

    full_fyers = re.fullmatch(r"(NSE|BSE):([A-Z0-9&-]+)-EQ", upper)
    if full_fyers:
        exchange, symbol = full_fyers.groups()
        return _remember(EquityInstrument(
            symbol=symbol,
            label=symbol,
            market="INDIA",
            exchange=exchange,
            provider="FYERS",
            provider_symbol=upper,
            currency="INR",
            data_quality="BROKER_SYMBOL_EXPLICIT",
        ))

    explicit_global = re.fullmatch(r"(?:YF|GLOBAL|NASDAQ|NYSE|AMEX):([A-Z0-9.^=-]+)", upper)
    if explicit_global:
        ticker = explicit_global.group(1)
        exchange = upper.split(":", 1)[0]
        if exchange in {"YF", "GLOBAL"}:
            exchange = "GLOBAL"
        return _remember(EquityInstrument(
            symbol=ticker,
            label=ticker,
            market="GLOBAL",
            exchange=exchange,
            provider="YAHOO_PUBLIC",
            provider_symbol=ticker,
            currency="UNKNOWN",
            data_quality="UNOFFICIAL_PUBLIC_DELAYED",
        ))

    compact_name = re.sub(r"[^A-Z0-9&]+", " ", upper).strip()
    india_alias = INDIA_NAME_ALIASES.get(compact_name)
    nifty = _nifty_index()
    if india_alias and india_alias in nifty:
        return _remember(nifty[india_alias])
    compact_symbol = upper.replace(" ", "")
    if compact_symbol in nifty:
        return _remember(nifty[compact_symbol])

    global_meta = GLOBAL_ALIASES.get(compact_name) or GLOBAL_ALIASES.get(compact_symbol)
    if global_meta:
        ticker, label, exchange = global_meta
        return _remember(EquityInstrument(
            symbol=ticker,
            label=label,
            market="GLOBAL",
            exchange=exchange,
            provider="YAHOO_PUBLIC",
            provider_symbol=ticker,
            currency="USD",
            data_quality="UNOFFICIAL_PUBLIC_DELAYED",
        ))

    # Unknown tickers are accepted only when the user explicitly specifies the
    # Indian exchange. Bare names are intentionally not guessed across world
    # exchanges because the same ticker can identify different securities.
    return None


def resolve_equity_symbols_from_text(text: str) -> tuple[str, ...]:
    value = " ".join(str(text or "").upper().replace("_", " ").split())
    found: list[str] = []

    aliases: list[tuple[str, str]] = list(INDIA_NAME_ALIASES.items())
    aliases.extend((name, meta[0]) for name, meta in GLOBAL_ALIASES.items())
    aliases.extend((row.symbol, row.symbol) for row in _fallback_constituents())
    for alias, symbol in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])", value):
            if symbol not in found:
                found.append(symbol)

    for match in re.finditer(r"\b(?:YF|GLOBAL|NASDAQ|NYSE|AMEX|NSE|BSE):[A-Z0-9.^&=-]+(?:-EQ)?\b", value):
        instrument = resolve_equity_symbol(match.group(0))
        if instrument and instrument.symbol not in found:
            found.append(instrument.symbol)

    ticker_match = re.search(r"\b(?:TICKER|SYMBOL)\s+([A-Z][A-Z0-9.^=-]{0,14})\b", value)
    if ticker_match:
        explicit = resolve_equity_symbol("GLOBAL:" + ticker_match.group(1))
        if explicit and explicit.symbol not in found:
            found.append(explicit.symbol)
    return tuple(found)


def equity_metadata(symbol: str) -> dict[str, Any] | None:
    instrument = resolve_equity_symbol(symbol)
    return instrument.to_dict() if instrument else None
