"""Canonical V16 trading workspace state assembled from the Quant runtime.

This module is intentionally a read-only convergence boundary.  It does not
create a second trading engine and it never talks to a broker order surface.
The Master/UI consume one snapshot while the existing Quant runtime remains
the authority for market data, paper positions, horizon mandates and scan
decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import json


QUANT_HOST = os.getenv("JARVIS_WORKSTATION_HOST", "127.0.0.1")
QUANT_PORT = int(os.getenv("JARVIS_WORKSTATION_PORT", "8787"))
QUANT_URL = f"http://{QUANT_HOST}:{QUANT_PORT}"

WORKSPACES = ("INTRADAY", "SWING", "INVESTMENT", "OPTIONS")
DEFAULT_SYMBOL = {
    "INTRADAY": "NIFTY",
    "SWING": "NIFTY",
    "INVESTMENT": "NIFTY",
    "OPTIONS": "NIFTY",
}
DEFAULT_TIMEFRAME = {
    "INTRADAY": "5m",
    "SWING": "1h",
    "INVESTMENT": "1d",
    "OPTIONS": "5m",
}
_TIMEFRAME_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}

JsonClient = Callable[[str, dict[str, Any] | None, float], dict[str, Any] | None]


def _safe_message(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ")[:700]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _quant_json(
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = 3.0,
) -> dict[str, Any] | None:
    suffix = str(path or "")
    if not suffix.startswith("/"):
        suffix = "/" + suffix
    if params:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        suffix = f"{suffix}?{query}"
    request = urllib.request.Request(
        QUANT_URL + suffix,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(0.2, float(timeout))) as response:
            value = json.loads(response.read().decode("utf-8", errors="replace"))
        return value if isinstance(value, dict) else None
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def _workspace(value: str | None) -> str:
    normalized = str(value or "INTRADAY").strip().upper()
    if normalized not in WORKSPACES:
        raise ValueError(
            "workspace must be INTRADAY, SWING, INVESTMENT or OPTIONS"
        )
    return normalized


def _symbol(value: str | None, workspace: str) -> str:
    normalized = str(value or DEFAULT_SYMBOL[workspace]).strip().upper()
    if not normalized:
        raise ValueError("symbol is required")
    return normalized[:80]


def _timeframe(value: str | None, workspace: str) -> str:
    normalized = str(value or DEFAULT_TIMEFRAME[workspace]).strip().lower()
    if normalized not in _TIMEFRAME_SECONDS:
        raise ValueError(
            "timeframe must be one of 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h or 1d"
        )
    return normalized


def _provider_health(provider: dict[str, Any]) -> dict[str, Any]:
    state = str(provider.get("state") or "UNAVAILABLE").strip().upper()
    bridge = _dict(provider.get("bridge"))
    retry_after = _first(provider, "retry_after_seconds", "retry_in_seconds")
    if retry_after is None:
        retry_after = _first(bridge, "retry_after_seconds", "retry_in_seconds")

    entry_allowed = state == "CONNECTED"
    if state == "CONNECTED":
        human = "FYERS connected"
        severity = "OK"
    elif state == "LOGIN_REQUIRED":
        human = "FYERS login required"
        severity = "BLOCKED"
    elif state in {"RATE_LIMITED", "COOLDOWN", "THROTTLED"}:
        human = "FYERS rate limited"
        if retry_after is not None:
            human += f" · retry in {retry_after} sec"
        severity = "DEGRADED"
    elif state in {"CONNECTING", "STARTING"}:
        human = "FYERS connecting"
        severity = "DEGRADED"
    elif state in {"SESSION_UNAVAILABLE", "TOKEN_EXPIRED", "AUTH_FAILED"}:
        human = "FYERS session unavailable"
        severity = "BLOCKED"
    else:
        human = "FYERS unavailable"
        severity = "BLOCKED"

    return {
        "provider": str(provider.get("provider") or "FYERS"),
        "state": state,
        "severity": severity,
        "human_state": human,
        "configured": bool(provider.get("configured")),
        "token_saved": bool(provider.get("token_saved")),
        "retry_after_seconds": retry_after,
        "new_entries_allowed": entry_allowed,
        "raw": provider,
    }


def _last_candle_epoch(candles: list[dict[str, Any]]) -> float | None:
    if not candles:
        return None
    row = candles[-1]
    value = _first(row, "close_time", "time", "timestamp")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 10_000_000_000:
        number /= 1000.0
    return number


def _chart_health(
    payload: dict[str, Any],
    timeframe: str,
    *,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    candles = _rows(payload.get("candles"))
    success = bool(payload.get("success") and candles)
    last_epoch = _last_candle_epoch(candles)
    age_seconds: float | None = None
    state = "UNAVAILABLE"
    if success and last_epoch is not None:
        current = float(now_epoch if now_epoch is not None else time.time())
        age_seconds = max(0.0, current - last_epoch)
        interval = float(_TIMEFRAME_SECONDS[timeframe])
        state = "FRESH" if age_seconds <= interval * 2.25 else "STALE"
    elif success:
        state = "FRESH"

    source = str(payload.get("source") or "UNAVAILABLE")
    message = str(payload.get("message") or "").strip()
    if state == "STALE":
        message = f"Last verified completed candle is {int(age_seconds or 0)} sec old."
    elif state == "UNAVAILABLE" and not message:
        message = "Verified candles unavailable."

    return {
        "state": state,
        "source": source,
        "data_quality": str(payload.get("data_quality") or "UNAVAILABLE"),
        "bars": len(candles),
        "last_completed_candle_epoch": last_epoch,
        "age_seconds": age_seconds,
        "message": message,
        "new_entries_allowed": state == "FRESH",
    }


def _position_rows(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    return _rows(
        _first(
            portfolio,
            "positions",
            "open_positions",
            "paper_positions",
        )
    )


def _workspace_positions(
    portfolio: dict[str, Any],
    workspace: str,
) -> list[dict[str, Any]]:
    positions = _position_rows(portfolio)
    if workspace == "OPTIONS":
        return [
            row
            for row in positions
            if "OPTION" in str(row.get("asset_type") or "").upper()
        ]
    result = []
    for row in positions:
        bucket = str(
            _first(row, "portfolio_bucket", "workspace", "mandate") or ""
        ).strip().upper()
        if bucket == workspace:
            result.append(row)
    return result


def _workspace_decisions(
    controller: dict[str, Any],
    workspace: str,
) -> list[dict[str, Any]]:
    board = _rows(controller.get("decision_board"))
    if workspace == "OPTIONS":
        return [
            row
            for row in board
            if "OPTION" in str(row.get("asset_type") or "").upper()
            or "OPTION" in str(row.get("lane") or "").upper()
        ]
    return [
        row
        for row in board
        if str(row.get("mandate") or "").strip().upper() == workspace
    ]


def _watchlist(
    controller: dict[str, Any],
    decisions: list[dict[str, Any]],
    workspace: str,
) -> list[str]:
    routing = _dict(controller.get("candidate_routing"))
    routing_key = {
        "INTRADAY": "intraday_symbols",
        "SWING": "swing_symbols",
        "INVESTMENT": "investment_symbols",
        "OPTIONS": "options_symbols",
    }[workspace]
    values = list(routing.get(routing_key) or [])
    values.extend(row.get("symbol") for row in decisions)
    result: list[str] = []
    for value in values:
        symbol = str(value or "").strip().upper()
        if symbol and symbol not in result:
            result.append(symbol)
    return result[:40]


def _setup_from_decisions(
    decisions: list[dict[str, Any]],
    selected_symbol: str,
) -> dict[str, Any]:
    selected = next(
        (
            row
            for row in decisions
            if str(row.get("symbol") or "").strip().upper() == selected_symbol
        ),
        decisions[0] if decisions else None,
    )
    if not selected:
        return {
            "state": "NONE",
            "symbol": selected_symbol,
            "reason": "No canonical Quant decision is currently available.",
        }

    hard = list(selected.get("hard_blockers") or selected.get("blockers") or [])
    actionable = bool(selected.get("qualified")) and not hard
    return {
        "state": "ACTIONABLE" if actionable else "REJECTED",
        "symbol": str(selected.get("symbol") or selected_symbol),
        "direction": _first(
            selected,
            "candidate_side",
            "adaptive_side",
            "direction",
        ),
        "entry": _first(selected, "entry", "entry_price", "proposed_entry"),
        "stop": _first(selected, "stop", "stop_price", "proposed_stop"),
        "target": _first(selected, "target", "target_price", "proposed_target"),
        "expected_value_r": _first(
            selected,
            "adaptive_expected_value_r",
            "expected_value_r",
            "ev_r",
        ),
        "confidence": _first(
            selected,
            "adaptive_confidence",
            "confidence",
        ),
        "execution_score": selected.get("execution_score"),
        "hard_blockers": hard,
        "soft_evidence": list(selected.get("soft_evidence") or []),
        "primary_blocker": selected.get("primary_blocker") or (hard[0] if hard else None),
        "message": selected.get("message"),
        "source": "QUANT_DECISION_BOARD",
        "raw": selected,
    }


def _capital(
    portfolio: dict[str, Any],
    controller: dict[str, Any],
    workspace: str,
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    equity = _number(
        _first(
            portfolio,
            "equity",
            "current_equity",
            "paper_equity",
            "account_equity",
        )
    )
    allocations = _dict(controller.get("allocations"))
    fraction = _number(allocations.get(workspace))
    allocated = equity * fraction if equity is not None and fraction is not None else None

    committed = 0.0
    at_risk = 0.0
    unrealized_from_positions = 0.0
    have_committed = False
    have_risk = False
    have_unrealized = False
    for row in positions:
        value = _number(_first(row, "notional", "capital_committed", "committed_capital"))
        if value is not None:
            committed += abs(value)
            have_committed = True
        value = _number(_first(row, "risk_at_stop", "capital_at_risk", "risk"))
        if value is not None:
            at_risk += abs(value)
            have_risk = True
        value = _number(row.get("unrealized_pnl"))
        if value is not None:
            unrealized_from_positions += value
            have_unrealized = True

    committed_value = committed if have_committed else None
    risk_value = at_risk if have_risk else None
    available = (
        max(0.0, allocated - committed_value)
        if allocated is not None and committed_value is not None
        else None
    )
    return {
        "workspace_equity": allocated,
        "allocation_fraction": fraction,
        "available_capital": available,
        "committed_capital": committed_value,
        "capital_at_risk": risk_value,
        "realized_pnl": _number(
            _first(portfolio, "realized_pnl", "booked_pnl")
        ),
        "unrealized_pnl": (
            unrealized_from_positions
            if have_unrealized
            else _number(portfolio.get("unrealized_pnl"))
        ),
        "global_equity": equity,
        "source": "PAPER_DESK_AND_PORTFOLIO_CONTROLLER",
    }


def build_workspace_state(
    workspace: str = "INTRADAY",
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    include_chart: bool = True,
    client: JsonClient = _quant_json,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    """Return one UI-safe snapshot without inventing missing runtime evidence."""

    bucket = _workspace(workspace)
    selected_symbol = _symbol(symbol, bucket)
    selected_timeframe = _timeframe(timeframe, bucket)
    captured_at = datetime.now(timezone.utc).isoformat()

    health = _dict(client("/api/health", None, 1.5))
    provider = _dict(client("/api/provider", None, 2.0))
    controller = _dict(client("/api/paper/portfolio-controller", None, 2.5))
    portfolio = _dict(client("/api/paper/portfolio", None, 3.0))
    scanner = _dict(client("/api/scanner/multi", None, 2.5))
    autonomy = _dict(client("/api/paper/autonomy", None, 2.0))

    candles = {}
    if include_chart:
        candles = _dict(
            client(
                "/api/candles",
                {
                    "symbol": selected_symbol,
                    "timeframe": selected_timeframe,
                    "bars": 320,
                },
                8.0,
            )
        )

    provider_health = _provider_health(provider)
    chart_health = (
        _chart_health(candles, selected_timeframe, now_epoch=now_epoch)
        if include_chart
        else {
            "state": "NOT_REQUESTED",
            "source": None,
            "data_quality": None,
            "bars": 0,
            "last_completed_candle_epoch": None,
            "age_seconds": None,
            "message": "Chart payload not requested.",
            "new_entries_allowed": True,
        }
    )

    mandates = _dict(controller.get("mandates"))
    mandate = _dict(mandates.get(bucket))
    positions = _workspace_positions(portfolio, bucket)
    decisions = _workspace_decisions(controller, bucket)
    setup = _setup_from_decisions(decisions, selected_symbol)
    watchlist = _watchlist(controller, decisions, bucket)

    quant_reachable = bool(health or controller or portfolio)
    data_valid = bool(
        chart_health.get("new_entries_allowed")
        and (
            provider_health.get("new_entries_allowed")
            or str(chart_health.get("source") or "").upper()
            in {"BINANCE_PUBLIC", "YAHOO_FINANCE", "YFINANCE"}
        )
    )
    entry_permission = bool(
        quant_reachable
        and data_valid
        and bucket != "OPTIONS"
        and bool(mandate.get("running"))
    )

    degradation: list[str] = []
    if not quant_reachable:
        degradation.append("QUANT_RUNTIME_UNAVAILABLE")
    if provider_health["state"] != "CONNECTED":
        degradation.append(f"FYERS_{provider_health['state']}")
    if include_chart and chart_health["state"] != "FRESH":
        degradation.append(f"CHART_DATA_{chart_health['state']}")
    if bucket == "OPTIONS":
        degradation.append("OPTIONS_WORKSPACE_CONVERGENCE_PENDING")

    return {
        "success": quant_reachable,
        "version": "16.0",
        "contract": "JARVIS_V16_CANONICAL_TRADING_WORKSPACE_STATE",
        "snapshot_at": captured_at,
        "state_quality": "CANONICAL_RUNTIME" if quant_reachable else "DEGRADED_UNAVAILABLE",
        "workspace": bucket,
        "session": {
            "running": bool(mandate.get("running")),
            "all_mandates_running": bool(controller.get("all_running")),
            "active_mandates": list(controller.get("active_mandates") or []),
            "new_entries_allowed": entry_permission,
            "position_management_remains_active": bool(positions),
            "message": mandate.get("message") or controller.get("message"),
        },
        "capital": _capital(portfolio, controller, bucket, positions),
        "market_data": {
            "provider": provider_health,
            "chart": chart_health,
            "data_valid": data_valid,
            "degraded": bool(degradation),
            "degradation_reasons": degradation,
            "rule": (
                "No fabricated candles. New paper entries require verified data; "
                "existing paper positions remain visible/manageable in degraded mode."
            ),
        },
        "watchlist": watchlist,
        "selected_instrument": {
            "symbol": selected_symbol,
            "timeframe": selected_timeframe,
            "workspace": bucket,
        },
        "chart": {
            "symbol": selected_symbol,
            "timeframe": selected_timeframe,
            "candles": _rows(candles.get("candles")) if include_chart else [],
            "source": chart_health.get("source"),
            "data_quality": chart_health.get("data_quality"),
            "health": chart_health.get("state"),
        },
        "proposed_setup": setup,
        "positions": positions,
        "orders": [],
        "scan_decisions": decisions,
        "risk": {
            "new_entries_allowed": entry_permission,
            "hard_blockers": list(setup.get("hard_blockers") or []),
            "portfolio_controller": {
                "allocation_fraction": _dict(controller.get("allocations")).get(bucket),
                "running": bool(mandate.get("running")),
            },
        },
        "execution_trace": {
            "available": False,
            "events": [],
            "reason": "Canonical execution-event endpoint is not yet exposed by Quant runtime.",
        },
        "availability": {
            "orders": False,
            "execution_trace": False,
            "scanner": bool(scanner),
            "portfolio": bool(portfolio),
            "portfolio_controller": bool(controller),
            "autonomy": bool(autonomy),
        },
        "runtime": {
            "quant": health,
            "scanner": scanner,
            "autonomy": autonomy,
        },
        "safety": {
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "naked_option_selling": False,
            "live_orders_locked": True,
            "investment_long_only": True,
        },
    }


__all__ = [
    "WORKSPACES",
    "build_workspace_state",
]
