"""Verified publisher adapters for the canonical JARVIS market event bus.

Adapters reject missing provenance, stale/unverified inputs, and malformed event
payloads.  They do not fetch data and never create substitute market values.
"""

from __future__ import annotations

from typing import Any, Mapping

from workstation.market_data_contract import (
    MarketDataQuality,
    MarketEventType,
    canonical_market_event,
)
from workstation.market_event_bus import MARKET_EVENT_BUS, MarketEventBus


def _source(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    provider = str(result.get("provider") or result.get("source") or "").strip()
    symbol = str(result.get("provider_symbol") or result.get("symbol") or "").strip()
    if not provider or not symbol:
        raise ValueError("Verified market events require provider and provider symbol provenance.")
    if result.get("success") is not True and result.get("verified") is not True:
        raise ValueError("Unverified provider payload cannot be published as a market event.")
    if result.get("stale") is True:
        raise ValueError("Stale provider payload cannot be published as a current market event.")
    result.setdefault("success", True)
    result.setdefault("verified", True)
    if not result.get("data_quality") and not result.get("quality_flag"):
        raise ValueError("Provider payload must declare an explicit market-data quality flag.")
    return result


def _publish(
    source: Mapping[str, Any],
    event_payload: Mapping[str, Any],
    event_type: MarketEventType,
    *,
    timeframe: str = "tick",
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    event = canonical_market_event(
        _source(source),
        dict(event_payload),
        event_type=event_type,
        timeframe=timeframe,
    )
    return bus.publish(event)


def publish_option_chain(
    source: Mapping[str, Any],
    contracts: list[dict[str, Any]],
    *,
    expiry: str | None = None,
    spot: float | None = None,
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    if not isinstance(contracts, list):
        raise ValueError("Option chain contracts must be a list.")
    return _publish(
        source,
        {"contracts": contracts, "expiry": expiry, "spot": spot},
        MarketEventType.OPTION_CHAIN_SNAPSHOT,
        bus=bus,
    )


def publish_open_interest(
    source: Mapping[str, Any],
    open_interest: float,
    *,
    change: float | None = None,
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"open_interest": float(open_interest)}
    if change is not None:
        payload["change"] = float(change)
    return _publish(source, payload, MarketEventType.OPEN_INTEREST_UPDATE, bus=bus)


def publish_volatility(
    source: Mapping[str, Any],
    volatility: float,
    *,
    kind: str = "IMPLIED_OR_REALIZED",
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    return _publish(
        source,
        {"volatility": float(volatility), "kind": str(kind)},
        MarketEventType.VOLATILITY_UPDATE,
        bus=bus,
    )


def publish_greeks(
    source: Mapping[str, Any],
    *,
    delta: float,
    gamma: float | None = None,
    theta: float | None = None,
    vega: float | None = None,
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"delta": float(delta)}
    for name, value in (("gamma", gamma), ("theta", theta), ("vega", vega)):
        if value is not None:
            payload[name] = float(value)
    return _publish(source, payload, MarketEventType.GREEKS_UPDATE, bus=bus)


def publish_order_book(
    source: Mapping[str, Any],
    *,
    bids: list[Any],
    asks: list[Any],
    delta: bool = False,
    sequence: int | None = None,
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"bids": list(bids), "asks": list(asks)}
    if sequence is not None:
        payload["sequence"] = int(sequence)
    return _publish(
        source,
        payload,
        MarketEventType.ORDER_BOOK_DELTA if delta else MarketEventType.ORDER_BOOK_SNAPSHOT,
        bus=bus,
    )


def publish_news_macro(
    source: Mapping[str, Any],
    *,
    headline: str,
    url: str | None = None,
    published_at: str | None = None,
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    clean = str(headline or "").strip()
    if not clean:
        raise ValueError("News/macro headline is required.")
    return _publish(
        source,
        {"headline": clean[:1000], "url": str(url or "") or None, "published_at": published_at},
        MarketEventType.NEWS_MACRO_EVENT,
        bus=bus,
    )


def publish_provider_health(
    *,
    provider: str,
    status: str,
    symbol: str = "PROVIDER",
    detail: str = "",
    bus: MarketEventBus = MARKET_EVENT_BUS,
) -> dict[str, Any]:
    normalized = str(status or "").strip().upper()
    if normalized not in {"READY", "DEGRADED", "DOWN"}:
        raise ValueError("Provider health must be READY, DEGRADED or DOWN.")
    source = {
        "provider": str(provider or "").strip(),
        "provider_symbol": str(symbol or "PROVIDER"),
        "success": True,
        "verified": True,
        "stale": False,
        "data_quality": MarketDataQuality.PUBLIC_LIVE.value,
    }
    return _publish(
        source,
        {"status": normalized, "detail": str(detail or "")[:500]},
        MarketEventType.PROVIDER_HEALTH,
        bus=bus,
    )


__all__ = [
    "publish_greeks",
    "publish_news_macro",
    "publish_open_interest",
    "publish_option_chain",
    "publish_order_book",
    "publish_provider_health",
    "publish_volatility",
]
