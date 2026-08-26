"""Canonical, fail-closed market-data and venue-session contracts.

The contract normalizes provenance and freshness only.  It never fetches data,
places orders, or upgrades an unverified provider response into verified data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from enum import Enum
import math
import os
from typing import Any, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo


UTC = timezone.utc
INDIA_TZ = ZoneInfo("Asia/Kolkata")


class MarketDataQuality(str, Enum):
    BROKER_LIVE = "BROKER_LIVE"
    BROKER_HISTORICAL = "BROKER_HISTORICAL"
    PUBLIC_LIVE = "PUBLIC_LIVE"
    PUBLIC_DELAYED = "PUBLIC_DELAYED"
    UNVERIFIED = "UNVERIFIED"


class MarketEventType(str, Enum):
    TRADE_TICK = "TRADE_TICK"
    QUOTE_TICK = "QUOTE_TICK"
    BAR = "BAR"
    ORDER_BOOK_SNAPSHOT = "ORDER_BOOK_SNAPSHOT"
    ORDER_BOOK_DELTA = "ORDER_BOOK_DELTA"
    OPTION_CHAIN_SNAPSHOT = "OPTION_CHAIN_SNAPSHOT"
    GREEKS_UPDATE = "GREEKS_UPDATE"
    OPEN_INTEREST_UPDATE = "OPEN_INTEREST_UPDATE"
    VOLATILITY_UPDATE = "VOLATILITY_UPDATE"
    NEWS_MACRO_EVENT = "NEWS_MACRO_EVENT"
    PROVIDER_HEALTH = "PROVIDER_HEALTH"


def _aware_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and math.isfinite(float(value)):
        raw = float(value)
        if raw > 10_000_000_000:
            raw /= 1_000.0
        parsed = datetime.fromtimestamp(raw, tz=UTC)
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class MarketDatum:
    event_type: str
    provider: str
    provider_symbol: str
    exchange_timestamp: str | None
    received_timestamp: str
    timeframe: str
    quality_flag: str
    stale: bool
    verified: bool
    freshness_basis: str

    def __post_init__(self) -> None:
        if self.event_type not in {item.value for item in MarketEventType}:
            raise ValueError("Unsupported market event type.")
        if not self.provider.strip() or not self.provider_symbol.strip():
            raise ValueError("Provider and provider symbol are required.")
        if self.quality_flag not in {item.value for item in MarketDataQuality}:
            raise ValueError("Unsupported market-data quality flag.")
        received = _aware_timestamp(self.received_timestamp)
        if received is None:
            raise ValueError("A timezone-aware received timestamp is required.")
        if self.verified and self.quality_flag == MarketDataQuality.UNVERIFIED.value:
            raise ValueError("Unverified quality cannot be marked verified.")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketEventEnvelope:
    """Validated provider-neutral event with provenance and typed payload."""

    event_id: str
    datum: MarketDatum
    payload: Mapping[str, Any]
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.event_id).strip() or not isinstance(self.payload, Mapping):
            raise ValueError("Market events require an identity and object payload.")
        kind = MarketEventType(self.datum.event_type)
        payload = self.payload
        numeric_requirements = {
            MarketEventType.TRADE_TICK: ("price", "quantity"),
            MarketEventType.QUOTE_TICK: ("ltp",),
            MarketEventType.BAR: ("open", "high", "low", "close"),
            MarketEventType.GREEKS_UPDATE: ("delta",),
            MarketEventType.OPEN_INTEREST_UPDATE: ("open_interest",),
            MarketEventType.VOLATILITY_UPDATE: ("volatility",),
        }
        for field in numeric_requirements.get(kind, ()):
            value = payload.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError(f"{kind.value} requires finite numeric {field}.")
        if kind == MarketEventType.BAR:
            if float(payload["high"]) < max(float(payload["open"]), float(payload["close"]), float(payload["low"])):
                raise ValueError("BAR high is inconsistent with OHLC values.")
            if float(payload["low"]) > min(float(payload["open"]), float(payload["close"]), float(payload["high"])):
                raise ValueError("BAR low is inconsistent with OHLC values.")
        if kind in {MarketEventType.ORDER_BOOK_SNAPSHOT, MarketEventType.ORDER_BOOK_DELTA}:
            if not isinstance(payload.get("bids"), list) or not isinstance(payload.get("asks"), list):
                raise ValueError("Order-book events require bids and asks arrays.")
        if kind == MarketEventType.OPTION_CHAIN_SNAPSHOT and not isinstance(payload.get("contracts"), list):
            raise ValueError("Option-chain events require a contracts array.")
        if kind == MarketEventType.PROVIDER_HEALTH and str(payload.get("status") or "").upper() not in {"READY", "DEGRADED", "DOWN"}:
            raise ValueError("Provider health status must be READY, DEGRADED or DOWN.")
        if kind == MarketEventType.NEWS_MACRO_EVENT and not str(payload.get("headline") or "").strip():
            raise ValueError("News/macro events require a headline.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id, "event_type": self.datum.event_type,
            "datum": self.datum.as_dict(), "payload": dict(self.payload),
            "correlation_id": self.correlation_id,
        }


def canonical_market_event(
    source: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    event_type: MarketEventType,
    timeframe: str = "tick",
    received_at: datetime | None = None,
    stale_after_seconds: float = 90.0,
    correlation_id: str | None = None,
) -> MarketEventEnvelope:
    return MarketEventEnvelope(
        event_id=uuid4().hex,
        datum=canonical_market_datum(
            source, event_type=event_type, timeframe=timeframe,
            received_at=received_at, stale_after_seconds=stale_after_seconds,
        ),
        payload=dict(payload),
        correlation_id=correlation_id,
    )


def canonical_market_datum(
    payload: Mapping[str, Any],
    *,
    event_type: MarketEventType = MarketEventType.QUOTE_TICK,
    timeframe: str = "tick",
    received_at: datetime | None = None,
    stale_after_seconds: float = 90.0,
) -> MarketDatum:
    received = _aware_timestamp(received_at or payload.get("received_timestamp") or payload.get("received_at"))
    received = received or datetime.now(UTC)
    exchange = _aware_timestamp(
        payload.get("exchange_timestamp")
        or payload.get("exchange_time")
        or payload.get("timestamp")
    )
    provider = str(payload.get("provider") or payload.get("source") or "").strip().upper()
    provider_symbol = str(payload.get("provider_symbol") or payload.get("symbol") or "").strip()
    quality = str(payload.get("quality_flag") or payload.get("data_quality") or "").strip().upper()
    if quality not in {item.value for item in MarketDataQuality}:
        if provider == "FYERS":
            quality = MarketDataQuality.BROKER_LIVE.value
        elif provider in {"BINANCE_PUBLIC", "BINANCE_PUBLIC_DATA"}:
            quality = MarketDataQuality.PUBLIC_LIVE.value
        elif "DELAY" in provider or payload.get("delayed") is True:
            quality = MarketDataQuality.PUBLIC_DELAYED.value
        else:
            quality = MarketDataQuality.UNVERIFIED.value
    freshness_basis = "EXCHANGE_TIMESTAMP" if exchange is not None else "RECEIVED_TIMESTAMP"
    reference = exchange or received
    age = max(0.0, (received - reference).total_seconds())
    stale = bool(payload.get("stale")) or age > max(1.0, float(stale_after_seconds))
    verified = bool(payload.get("success", payload.get("verified", False)))
    verified = verified and quality != MarketDataQuality.UNVERIFIED.value
    return MarketDatum(
        event_type=event_type.value,
        provider=provider,
        provider_symbol=provider_symbol,
        exchange_timestamp=exchange.isoformat() if exchange else None,
        received_timestamp=received.isoformat(),
        timeframe=str(timeframe or "tick"),
        quality_flag=quality,
        stale=stale,
        verified=verified,
        freshness_basis=freshness_basis,
    )


@dataclass(frozen=True)
class SessionStatus:
    venue: str
    timezone: str
    evaluated_at: str
    session_open: bool
    entry_eligible: bool
    reason: str
    calendar_source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class VenueSessionService:
    """One venue-aware session gate shared by scanners and Paper Desk."""

    def __init__(self, *, holidays: Mapping[str, set[date]] | None = None) -> None:
        self._holidays = {str(key).upper(): set(values) for key, values in (holidays or {}).items()}

    @staticmethod
    def venue_for(metadata: Mapping[str, Any]) -> str:
        asset_class = str(metadata.get("asset_class") or "").upper()
        if asset_class == "CRYPTO":
            return "CRYPTO_24_7"
        if asset_class in {"COMMODITY", "OPTION"}:
            return "MCX"
        if asset_class == "EQUITY" and str(metadata.get("market") or "").upper() != "INDIA":
            return "GLOBAL_RESEARCH_ONLY"
        exchange = str(metadata.get("exchange") or "").upper()
        if exchange == "BSE" or str(metadata.get("symbol") or "").upper() == "SENSEX":
            return "BSE"
        return "NSE"

    def _configured_holidays(self, venue: str) -> set[date]:
        configured = set(self._holidays.get(venue, set()))
        env_name = "JARVIS_INDIA_MARKET_HOLIDAYS" if venue in {"NSE", "BSE", "MCX"} else ""
        if env_name:
            for raw in os.getenv(env_name, "").split(","):
                try:
                    configured.add(date.fromisoformat(raw.strip()))
                except ValueError:
                    continue
        return configured

    def evaluate(self, venue: str, *, at: datetime | None = None) -> SessionStatus:
        normalized = str(venue or "").strip().upper()
        instant = _aware_timestamp(at) or datetime.now(UTC)
        if normalized == "CRYPTO_24_7":
            return SessionStatus(normalized, "UTC", instant.isoformat(), True, True, "CONTINUOUS_SESSION", "VENUE_CONTRACT")
        if normalized == "GLOBAL_RESEARCH_ONLY":
            return SessionStatus(normalized, "UNVERIFIED", instant.isoformat(), False, False, "NO_GOVERNED_EXCHANGE_CALENDAR", "FAIL_CLOSED")
        if normalized not in {"NSE", "BSE", "MCX"}:
            return SessionStatus(normalized or "UNKNOWN", "UNVERIFIED", instant.isoformat(), False, False, "UNKNOWN_VENUE", "FAIL_CLOSED")
        local = instant.astimezone(INDIA_TZ)
        if local.weekday() >= 5:
            return SessionStatus(normalized, str(INDIA_TZ), instant.isoformat(), False, False, "WEEKEND", "VENUE_CONTRACT")
        if local.date() in self._configured_holidays(normalized):
            return SessionStatus(normalized, str(INDIA_TZ), instant.isoformat(), False, False, "CONFIGURED_HOLIDAY", "CONFIGURED_CALENDAR")
        opening, closing = ((time(9, 0), time(23, 30)) if normalized == "MCX" else (time(9, 15), time(15, 30)))
        current = local.time().replace(tzinfo=None)
        is_open = opening <= current <= closing
        return SessionStatus(
            normalized,
            str(INDIA_TZ),
            instant.isoformat(),
            is_open,
            is_open,
            "REGULAR_SESSION" if is_open else "OUTSIDE_REGULAR_SESSION",
            "VENUE_CONTRACT",
        )


VENUE_SESSIONS = VenueSessionService()
