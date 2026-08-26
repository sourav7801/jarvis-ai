"""Normalized, read-only market universe definitions for JARVIS scanners.

This module is deliberately a foundation rather than an execution engine.  It
contains no broker account or order API.  Consumers receive explicit source,
session, data-quality and automatic-paper eligibility metadata and must still
verify a current market-data sample before creating synthetic exposure.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import json
from typing import Any, Callable, Iterable, Mapping, Sequence

from workstation.equity_universe import NIFTY50_CONSTITUENTS_URL, NIFTY50_FALLBACK


BANKNIFTY_CONSTITUENTS_URL = (
    "https://nsearchives.nseindia.com/content/indices/ind_niftybanklist.csv"
)
SENSEX_CONSTITUENTS_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/IndexConstituents/w?indexCode=16"
)

# Bounded exchange snapshots used only when the official runtime document is
# unavailable or malformed.  They are intentionally labelled as fallbacks so a
# UI cannot present them as a current exchange download.
BANKNIFTY_FALLBACK: tuple[tuple[str, str], ...] = (
    ("AUBANK", "AU Small Finance Bank Ltd."),
    ("AXISBANK", "Axis Bank Ltd."),
    ("BANKBARODA", "Bank of Baroda"),
    ("CANBK", "Canara Bank"),
    ("FEDERALBNK", "The Federal Bank Ltd."),
    ("HDFCBANK", "HDFC Bank Ltd."),
    ("ICICIBANK", "ICICI Bank Ltd."),
    ("IDFCFIRSTB", "IDFC First Bank Ltd."),
    ("INDUSINDBK", "IndusInd Bank Ltd."),
    ("KOTAKBANK", "Kotak Mahindra Bank Ltd."),
    ("PNB", "Punjab National Bank"),
    ("SBIN", "State Bank of India"),
)

SENSEX30_FALLBACK: tuple[tuple[str, str], ...] = (
    ("ADANIPORTS", "Adani Ports and Special Economic Zone Ltd."),
    ("ASIANPAINT", "Asian Paints Ltd."),
    ("AXISBANK", "Axis Bank Ltd."),
    ("BAJFINANCE", "Bajaj Finance Ltd."),
    ("BAJAJFINSV", "Bajaj Finserv Ltd."),
    ("BEL", "Bharat Electronics Ltd."),
    ("BHARTIARTL", "Bharti Airtel Ltd."),
    ("ETERNAL", "Eternal Ltd."),
    ("HCLTECH", "HCL Technologies Ltd."),
    ("HDFCBANK", "HDFC Bank Ltd."),
    ("HINDUNILVR", "Hindustan Unilever Ltd."),
    ("ICICIBANK", "ICICI Bank Ltd."),
    ("INDIGO", "InterGlobe Aviation Ltd."),
    ("INFY", "Infosys Ltd."),
    ("ITC", "ITC Ltd."),
    ("KOTAKBANK", "Kotak Mahindra Bank Ltd."),
    ("LT", "Larsen & Toubro Ltd."),
    ("M&M", "Mahindra & Mahindra Ltd."),
    ("MARUTI", "Maruti Suzuki India Ltd."),
    ("NTPC", "NTPC Ltd."),
    ("POWERGRID", "Power Grid Corporation of India Ltd."),
    ("RELIANCE", "Reliance Industries Ltd."),
    ("SBIN", "State Bank of India"),
    ("SUNPHARMA", "Sun Pharmaceutical Industries Ltd."),
    ("TATASTEEL", "Tata Steel Ltd."),
    ("TCS", "Tata Consultancy Services Ltd."),
    ("TECHM", "Tech Mahindra Ltd."),
    ("TITAN", "Titan Company Ltd."),
    ("TRENT", "Trent Ltd."),
    ("ULTRACEMCO", "UltraTech Cement Ltd."),
)


@dataclass(frozen=True)
class MarketSession:
    code: str
    timezone: str
    regular_open: str | None
    regular_close: str | None
    trading_days: tuple[str, ...]
    continuous: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trading_days"] = list(self.trading_days)
        return payload


INDIA_CASH_SESSION = MarketSession(
    "INDIA_CASH", "Asia/Kolkata", "09:15", "15:30", ("MON", "TUE", "WED", "THU", "FRI")
)
INDIA_COMMODITY_SESSION = MarketSession(
    "INDIA_COMMODITY", "Asia/Kolkata", "09:00", "23:30", ("MON", "TUE", "WED", "THU", "FRI")
)
US_EQUITY_SESSION = MarketSession(
    "US_EQUITY_REGULAR", "America/New_York", "09:30", "16:00", ("MON", "TUE", "WED", "THU", "FRI")
)
ALWAYS_OPEN_SESSION = MarketSession(
    "CRYPTO_24X7", "UTC", None, None, ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"), True
)


@dataclass(frozen=True)
class ScannerInstrument:
    symbol: str
    label: str
    asset_class: str
    market: str
    exchange: str
    provider: str
    provider_symbol: str
    currency: str
    session: MarketSession
    universe: tuple[str, ...]
    provenance: str
    data_quality: str
    auto_paper_eligible: bool
    eligibility_gate: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session"] = self.session.to_dict()
        payload["universe"] = list(self.universe)
        return payload


@dataclass(frozen=True)
class UniverseSnapshot:
    name: str
    instruments: tuple[ScannerInstrument, ...]
    authority: str
    source_url: str | None
    source_mode: str
    generated_at: str

    @property
    def official_runtime(self) -> bool:
        return self.source_mode == "OFFICIAL_RUNTIME"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "count": len(self.instruments),
            "authority": self.authority,
            "source_url": self.source_url,
            "source_mode": self.source_mode,
            "official_runtime": self.official_runtime,
            "generated_at": self.generated_at,
            "instruments": [item.to_dict() for item in self.instruments],
        }


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _india_equity(
    symbol: str,
    label: str,
    universe: str,
    provenance: str,
    *,
    exchange: str = "NSE",
    source_mode: str,
) -> ScannerInstrument:
    normalized = str(symbol).strip().upper()
    exchange = str(exchange).strip().upper()
    suffix = "-EQ" if exchange == "NSE" else "-A"
    return ScannerInstrument(
        symbol=normalized,
        label=str(label).strip() or normalized,
        asset_class="EQUITY",
        market="INDIA",
        exchange=exchange,
        provider="FYERS_READ_ONLY",
        provider_symbol=f"{exchange}:{normalized}{suffix}",
        currency="INR",
        session=INDIA_CASH_SESSION,
        universe=(universe,),
        provenance=provenance,
        data_quality=source_mode,
        auto_paper_eligible=True,
        eligibility_gate="CURRENT_BROKER_DATA_AND_OPEN_SESSION_REQUIRED",
    )


def _parse_nse_csv(text: str, universe: str, provenance: str) -> tuple[ScannerInstrument, ...]:
    rows = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    instruments: list[ScannerInstrument] = []
    for row in rows:
        normalized = {str(key).strip().lower(): value for key, value in row.items()}
        symbol = str(normalized.get("symbol") or "").strip().upper()
        label = str(normalized.get("company name") or symbol).strip()
        series = str(normalized.get("series") or "EQ").strip().upper()
        if symbol and series == "EQ":
            instruments.append(
                _india_equity(
                    symbol,
                    label,
                    universe,
                    provenance,
                    source_mode="OFFICIAL_RUNTIME",
                )
            )
    return tuple(instruments)


def _parse_sensex_json(text: str) -> tuple[ScannerInstrument, ...]:
    payload = json.loads(text)
    if isinstance(payload, Mapping):
        rows: Any = (
            payload.get("Table")
            or payload.get("table")
            or payload.get("data")
            or payload.get("Data")
            or payload.get("constituents")
        )
    else:
        rows = payload
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()
    instruments: list[ScannerInstrument] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = {str(key).lower(): value for key, value in row.items()}
        symbol = str(
            normalized.get("scrip_cd")
            or normalized.get("symbol")
            or normalized.get("scripcode")
            or ""
        ).strip().upper()
        label = str(
            normalized.get("long_name")
            or normalized.get("companyname")
            or normalized.get("scrip_name")
            or symbol
        ).strip()
        # BSE may return numeric scrip codes without a tradable broker alias.
        # Such rows are rejected rather than guessed.
        if symbol and not symbol.isdigit():
            instruments.append(
                _india_equity(
                    symbol,
                    label,
                    "SENSEX30",
                    "BSE",
                    exchange="BSE",
                    source_mode="OFFICIAL_RUNTIME",
                )
            )
    return tuple(instruments)


class ScannerUniverseRegistry:
    """Create normalized scanner universes without granting execution authority."""

    def __init__(self, configured_indian_equities: Iterable[str | Mapping[str, Any]] = ()) -> None:
        self.configured_indian_equities = tuple(configured_indian_equities)

    @staticmethod
    def _fallback(
        name: str,
        rows: Iterable[tuple[str, str]],
        authority: str,
        url: str,
    ) -> UniverseSnapshot:
        instruments = tuple(
            _india_equity(
                symbol,
                label,
                name,
                authority,
                source_mode="OFFICIAL_SNAPSHOT_FALLBACK",
            )
            for symbol, label in rows
        )
        return UniverseSnapshot(
            name, instruments, authority, url, "OFFICIAL_SNAPSHOT_FALLBACK", _generated_at()
        )

    def nifty50(self, loader: Callable[[str], str] | None = None) -> UniverseSnapshot:
        if loader is not None:
            try:
                instruments = _parse_nse_csv(loader(NIFTY50_CONSTITUENTS_URL), "NIFTY50", "NSE")
                if len(instruments) != 50:
                    raise ValueError("NIFTY50 official document did not contain exactly 50 EQ rows")
                return UniverseSnapshot(
                    "NIFTY50", instruments, "NSE", NIFTY50_CONSTITUENTS_URL,
                    "OFFICIAL_RUNTIME", _generated_at()
                )
            except Exception:
                pass
        return self._fallback(
            "NIFTY50",
            ((symbol, label) for symbol, label, _industry in NIFTY50_FALLBACK),
            "NSE",
            NIFTY50_CONSTITUENTS_URL,
        )

    def banknifty(self, loader: Callable[[str], str] | None = None) -> UniverseSnapshot:
        if loader is not None:
            try:
                instruments = _parse_nse_csv(loader(BANKNIFTY_CONSTITUENTS_URL), "BANKNIFTY", "NSE")
                if len(instruments) < 10:
                    raise ValueError("BANKNIFTY official document returned too few constituents")
                return UniverseSnapshot(
                    "BANKNIFTY", instruments, "NSE", BANKNIFTY_CONSTITUENTS_URL,
                    "OFFICIAL_RUNTIME", _generated_at()
                )
            except Exception:
                pass
        return self._fallback(
            "BANKNIFTY", BANKNIFTY_FALLBACK, "NSE", BANKNIFTY_CONSTITUENTS_URL
        )

    def sensex30(self, loader: Callable[[str], str] | None = None) -> UniverseSnapshot:
        if loader is not None:
            try:
                instruments = _parse_sensex_json(loader(SENSEX_CONSTITUENTS_URL))
                if len(instruments) != 30:
                    raise ValueError("SENSEX official document did not contain exactly 30 symbols")
                return UniverseSnapshot(
                    "SENSEX30", instruments, "BSE", SENSEX_CONSTITUENTS_URL,
                    "OFFICIAL_RUNTIME", _generated_at()
                )
            except Exception:
                pass
        return self._fallback(
            "SENSEX30", SENSEX30_FALLBACK, "BSE", SENSEX_CONSTITUENTS_URL
        )

    def configured_india(self) -> UniverseSnapshot:
        instruments: list[ScannerInstrument] = []
        for item in self.configured_indian_equities:
            if isinstance(item, Mapping):
                symbol = str(item.get("symbol") or "").strip().upper()
                label = str(item.get("label") or symbol).strip()
                exchange = str(item.get("exchange") or "NSE").strip().upper()
            else:
                value = str(item).strip().upper()
                if ":" in value:
                    exchange, symbol = value.split(":", 1)
                else:
                    exchange, symbol = "NSE", value
                symbol = symbol.removesuffix("-EQ").removesuffix("-A")
                label = symbol
            if symbol and exchange in {"NSE", "BSE"}:
                instruments.append(
                    _india_equity(
                        symbol,
                        label,
                        "INDIA_CONFIGURED",
                        "USER_CONFIGURATION",
                        exchange=exchange,
                        source_mode="EXPLICIT_BROKER_SYMBOL",
                    )
                )
        return UniverseSnapshot(
            "INDIA_CONFIGURED", tuple(instruments), "USER_CONFIGURATION", None,
            "EXPLICIT_CONFIGURATION", _generated_at()
        )

    @staticmethod
    def global_equities() -> UniverseSnapshot:
        rows = (
            ("AAPL", "Apple Inc.", "NASDAQ"),
            ("MSFT", "Microsoft Corporation", "NASDAQ"),
            ("GOOGL", "Alphabet Inc.", "NASDAQ"),
            ("AMZN", "Amazon.com Inc.", "NASDAQ"),
            ("NVDA", "NVIDIA Corporation", "NASDAQ"),
            ("META", "Meta Platforms Inc.", "NASDAQ"),
            ("TSLA", "Tesla Inc.", "NASDAQ"),
            ("JPM", "JPMorgan Chase & Co.", "NYSE"),
            ("BRK-B", "Berkshire Hathaway Inc.", "NYSE"),
        )
        instruments = tuple(
            ScannerInstrument(
                symbol, label, "EQUITY", "GLOBAL", exchange, "YAHOO_PUBLIC",
                symbol, "USD", US_EQUITY_SESSION, ("GLOBAL_MAJOR",),
                "PUBLIC_UNOFFICIAL", "UNOFFICIAL_DELAYED", False,
                "AUTO_PAPER_BLOCKED_UNOFFICIAL_OR_DELAYED_DATA",
            )
            for symbol, label, exchange in rows
        )
        return UniverseSnapshot(
            "GLOBAL_MAJOR", instruments, "PUBLIC_UNOFFICIAL", None,
            "UNOFFICIAL_DELAYED", _generated_at()
        )

    @staticmethod
    def crypto() -> UniverseSnapshot:
        rows = (
            ("BTC", "Bitcoin", "BTCUSDT"),
            ("ETH", "Ethereum", "ETHUSDT"),
            ("SOL", "Solana", "SOLUSDT"),
            ("BNB", "BNB", "BNBUSDT"),
            ("XRP", "XRP", "XRPUSDT"),
        )
        instruments = tuple(
            ScannerInstrument(
                symbol, label, "CRYPTO", "GLOBAL", "CRYPTO_SPOT",
                "BINANCE_PUBLIC_MARKET_DATA", provider_symbol, "USDT",
                ALWAYS_OPEN_SESSION, ("CRYPTO_MAJOR",), "BINANCE_PUBLIC",
                "PUBLIC_REALTIME_MARKET_DATA", True,
                "CURRENT_PUBLIC_DATA_AND_SYNTHETIC_PAPER_ONLY",
            )
            for symbol, label, provider_symbol in rows
        )
        return UniverseSnapshot(
            "CRYPTO_MAJOR", instruments, "BINANCE_PUBLIC", None,
            "PUBLIC_REALTIME_MARKET_DATA", _generated_at()
        )

    @staticmethod
    def commodities() -> UniverseSnapshot:
        rows = (
            ("CRUDEOIL", "Crude Oil Mini", "CRUDEOILM"),
            ("GOLD", "Gold Mini", "GOLDM"),
            ("SILVER", "Silver Mini", "SILVERM"),
            ("NATURALGAS", "Natural Gas Mini", "NATGASMINI"),
        )
        instruments = tuple(
            ScannerInstrument(
                symbol, label, "COMMODITY", "INDIA", "MCX", "FYERS_READ_ONLY",
                root, "INR", INDIA_COMMODITY_SESSION, ("MCX_MAJOR",),
                "FYERS_MCX_SYMBOL_MASTER", "BROKER_SYMBOL_RESOLUTION_REQUIRED",
                True, "ACTIVE_CONTRACT_CURRENT_BROKER_DATA_AND_OPEN_SESSION_REQUIRED",
            )
            for symbol, label, root in rows
        )
        return UniverseSnapshot(
            "MCX_MAJOR", instruments, "FYERS_MCX_SYMBOL_MASTER", None,
            "BROKER_SYMBOL_RESOLUTION_REQUIRED", _generated_at()
        )

    @staticmethod
    def indices() -> UniverseSnapshot:
        rows = (
            ("NIFTY", "NIFTY 50", "NSE:NIFTY50-INDEX"),
            ("BANKNIFTY", "NIFTY BANK", "NSE:NIFTYBANK-INDEX"),
            ("SENSEX", "S&P BSE SENSEX", "BSE:SENSEX-INDEX"),
        )
        instruments = tuple(
            ScannerInstrument(
                symbol, label, "INDEX", "INDIA", "NSE" if symbol != "SENSEX" else "BSE",
                "FYERS_READ_ONLY", provider_symbol, "INR", INDIA_CASH_SESSION,
                ("INDIA_INDICES",), "EXCHANGE_INDEX_VIA_FYERS",
                "BROKER_READ_ONLY", True,
                "CURRENT_BROKER_DATA_AND_OPEN_SESSION_REQUIRED",
            )
            for symbol, label, provider_symbol in rows
        )
        return UniverseSnapshot(
            "INDIA_INDICES", instruments, "NSE_AND_BSE_VIA_FYERS", None,
            "BROKER_READ_ONLY", _generated_at()
        )

    def catalog(self) -> dict[str, UniverseSnapshot]:
        """Return the bounded offline-safe catalog using labelled fallbacks."""

        return {
            "INDIA_INDICES": self.indices(),
            "NIFTY50": self.nifty50(),
            "BANKNIFTY": self.banknifty(),
            "SENSEX30": self.sensex30(),
            "INDIA_CONFIGURED": self.configured_india(),
            "GLOBAL_MAJOR": self.global_equities(),
            "CRYPTO_MAJOR": self.crypto(),
            "MCX_MAJOR": self.commodities(),
        }

    def normalized_registry(self) -> dict[str, Any]:
        catalog = self.catalog()
        return {
            "success": True,
            "mode": "READ_ONLY_DATA_AND_SYNTHETIC_PAPER",
            "live_execution": False,
            "universe_count": len(catalog),
            "instrument_count": sum(len(item.instruments) for item in catalog.values()),
            "universes": {name: snapshot.to_dict() for name, snapshot in catalog.items()},
            "guardrails": {
                "global_unofficial_data_auto_paper": "BLOCKED",
                "broker_order_api": "NOT_PRESENT",
                "new_exposure_requires_current_data": True,
                "new_exposure_requires_open_session": True,
            },
        }


DEFAULT_SCANNER_UNIVERSE_REGISTRY = ScannerUniverseRegistry()


def scanner_universe_registry(
    configured_indian_equities: Iterable[str | Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Public JSON-safe registry entry point used by future scanner adapters."""

    return ScannerUniverseRegistry(configured_indian_equities).normalized_registry()
