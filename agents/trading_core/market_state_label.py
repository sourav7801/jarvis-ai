
from __future__ import annotations

from datetime import datetime
from typing import Any


def classify_market_state(
    state: dict[str, Any],
    market_is_open: bool,
) -> dict[str, Any]:
    """
    Clearly marks whether the analysis is a live-session state or a historical
    baseline. This prevents a Sunday/holiday snapshot from sounding like a
    fresh live setup.
    """
    if market_is_open:
        return {
            "mode": "LIVE",
            "label": "LIVE_MARKET",
            "tradable": True,
            "reason": "Exchange session is open.",
        }

    return {
        "mode": "HISTORICAL_BASELINE",
        "label": "CLOSED_MARKET_BASELINE",
        "tradable": False,
        "reason": "Exchange session is closed; using the latest completed session.",
    }


def annotate(state: dict[str, Any], market_info: dict[str, Any]) -> dict[str, Any]:
    statuses = market_info.get("segmentStatus") or {}
    open_now = any(
        str(v).upper() in {"NORMAL", "OPEN"}
        for v in statuses.values()
    )

    return {
        "market_state": classify_market_state(
            state,
            market_is_open=open_now,
        ),
    }
