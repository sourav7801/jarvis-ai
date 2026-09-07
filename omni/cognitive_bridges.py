"""Safe adapters from existing JARVIS event sources into the V9.3 cognitive bus."""
from __future__ import annotations

from threading import RLock
from typing import Any

from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS, CognitiveEventType
from omni.world_model import WORLD_MODEL


_lock = RLock()
_installed = False


def _market_to_cognitive(event: Any) -> None:
    datum = getattr(event, "datum", None)
    if datum is None:
        return
    event_type = str(getattr(datum, "event_type", "") or "")
    provider = str(getattr(datum, "provider", "") or "UNKNOWN")
    symbol = str(getattr(datum, "provider_symbol", "") or "UNKNOWN")
    stale = bool(getattr(datum, "stale", True))
    verified = bool(getattr(datum, "verified", False))
    timeframe = str(getattr(datum, "timeframe", "") or "")
    payload = dict(getattr(event, "payload", {}) or {})
    correlation_id = getattr(event, "correlation_id", None)
    provenance = {
        "market_event_id": getattr(event, "event_id", None),
        "provider": provider,
        "verified": verified,
        "stale": stale,
        "timeframe": timeframe,
        "quality_flag": getattr(datum, "quality_flag", None),
        "exchange_timestamp": getattr(datum, "exchange_timestamp", None),
        "received_timestamp": getattr(datum, "received_timestamp", None),
    }

    if stale:
        kind = CognitiveEventType.MARKET_DATA_STALE
    elif event_type == "BAR" and verified:
        kind = CognitiveEventType.MARKET_BAR_COMPLETED
    elif event_type == "PROVIDER_HEALTH":
        status = str(payload.get("status") or "").upper()
        kind = {
            "READY": CognitiveEventType.PROVIDER_READY,
            "DEGRADED": CognitiveEventType.PROVIDER_DEGRADED,
            "DOWN": CognitiveEventType.PROVIDER_DOWN,
        }.get(status)
        if kind is None:
            return
    else:
        # The cognitive bus intentionally does not duplicate every market tick.
        # High-frequency observations remain on MarketEventBus.
        return

    COGNITIVE_EVENT_BUS.publish(
        kind,
        source="workstation.market_event_bus",
        subject=f"{provider}:{symbol}:{timeframe or 'tick'}",
        payload={
            "market_event_type": event_type,
            "provider": provider,
            "symbol": symbol,
            "timeframe": timeframe,
            "verified": verified,
            "stale": stale,
            "payload": payload,
        },
        provenance=provenance,
        correlation_id=correlation_id,
    )


def install_cognitive_bridges() -> dict[str, Any]:
    global _installed
    with _lock:
        if _installed:
            return {
                "success": True,
                "installed": True,
                "idempotent": True,
                "paper_only": True,
                "live_execution": False,
            }
        from workstation.market_event_bus import MARKET_EVENT_BUS

        MARKET_EVENT_BUS.subscribe("v93-cognitive-bridge", _market_to_cognitive)
        # Importing WORLD_MODEL installs its cognitive-event subscriber. The
        # reference is retained here to make that dependency explicit.
        _ = WORLD_MODEL
        _installed = True
        return {
            "success": True,
            "installed": True,
            "market_bridge": True,
            "world_model_subscriber": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


def status() -> dict[str, Any]:
    return {
        "success": True,
        "version": "9.3",
        "installed": _installed,
        "market_to_cognitive": _installed,
        "world_model_subscriber": _installed,
        "external_actions": "APPROVAL_GATED",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


try:
    install_cognitive_bridges()
except Exception:
    # Optional bridge installation must not prevent JARVIS import/startup.
    pass


__all__ = ["install_cognitive_bridges", "status"]
