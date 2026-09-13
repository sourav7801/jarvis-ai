"""V16 manual long-option paper execution on the canonical Paper Desk.

This module deliberately has no broker-order surface.  It validates an exact
FYERS-listed option contract against the daily symbol master, requires a fresh
verified quote plus explicit stop/target geometry, and then delegates admission,
sizing, accounting and journalling to the existing PaperTradingDesk/workspace
controller.  Naked short options and live orders are not represented here.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

from workstation import workspace_accounts as accounts


_MASTER_URLS = {
    "NSE": "https://public.fyers.in/sym_details/NSE_FO_sym_master.json",
    "BSE": "https://public.fyers.in/sym_details/BSE_FO_sym_master.json",
}
_MASTER_CACHE_TTL = 21_600.0
_MASTER_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_MASTER_LOCK = threading.RLock()
_OPTION_SYMBOL = re.compile(r"^(NSE|BSE):[A-Z0-9._-]+(CE|PE)$")


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _safe_text(value: Any, limit: int = 400) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ")[:limit]


def _failure(reason: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "success": False,
        "reason": reason,
        "message": message,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "live_orders_locked": True,
        "naked_option_selling": False,
        **extra,
    }


def _load_master(exchange: str) -> dict[str, Any]:
    key = str(exchange or "").upper()
    url = _MASTER_URLS.get(key)
    if not url:
        raise ValueError("Only FYERS NSE/BSE listed options are supported here.")
    now = time.monotonic()
    with _MASTER_LOCK:
        cached = _MASTER_CACHE.get(key)
        if cached and now - cached[0] <= _MASTER_CACHE_TTL:
            return cached[1]
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-V16-Paper-Options/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(40_000_000)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("FYERS symbol master did not return an object.")
    with _MASTER_LOCK:
        _MASTER_CACHE[key] = (now, payload)
    return payload


def option_instrument_spec(symbol: str) -> dict[str, Any]:
    """Return a provider-verified accounting spec for one exact option symbol."""
    requested = str(symbol or "").strip().upper()
    match = _OPTION_SYMBOL.fullmatch(requested)
    if not match:
        raise ValueError("Select an exact NSE/BSE CE or PE option contract.")
    exchange, suffix = match.groups()
    record = _load_master(exchange).get(requested)
    if not isinstance(record, dict):
        raise RuntimeError("Selected option is not present in today's FYERS symbol master.")
    lot = _number(record.get("minLotSize"), 0.0) or 0.0
    tick = _number(record.get("tickSize"), 0.0) or 0.0
    opt_type = str(record.get("optType") or suffix).upper()
    ticker = str(record.get("symTicker") or requested).upper()
    if ticker != requested or opt_type != suffix or lot <= 0 or tick <= 0:
        raise RuntimeError("FYERS option contract metadata is incomplete or mismatched.")
    return {
        "symbol": requested,
        "provider_symbol": requested,
        "asset_class": "OPTION",
        "instrument_type": "OPTION",
        "native_currency": "INR",
        "valuation_currency": "INR",
        # Paper Desk quantity is expressed in lots; multiplier converts each lot
        # into provider-reported underlying units for P&L/risk accounting.
        "quantity_step": 1.0,
        "contract_multiplier": lot,
        "tick_size": tick,
        "source": f"FYERS_{exchange}_FO_SYMBOL_MASTER",
        "verified": True,
        "verification_reason": "FYERS_DAILY_SYMBOL_MASTER_EXACT_MATCH",
        "cost_model_status": "CONFIGURABLE_CONSERVATIVE_PAPER_ESTIMATE",
        "expiry": record.get("expiryDate"),
        "strike": record.get("strikePrice"),
        "option_type": opt_type,
        "lot_size": lot,
    }


def _certificate(runtime: Any, symbol: str) -> dict[str, Any]:
    result = runtime.mark_loader(symbol)
    if not isinstance(result, dict):
        return {"success": False, "reason": "DATA_UNAVAILABLE"}
    # live_mark_snapshot already returns a strict quote certificate.  Keep it
    # intact rather than weakening or reinterpreting its freshness/session gate.
    return dict(result)


def _open_positions(runtime: Any, workspace: str) -> list[dict[str, Any]]:
    try:
        return list(runtime.snapshot(workspace).get("account", {}).get("positions") or [])
    except Exception:
        return []


def option_order(runtime: Any, body: dict[str, Any]) -> dict[str, Any]:
    """Execute a PAPER-only long-option entry or close through the canonical desk."""
    action = str(body.get("action") or "").strip().upper()
    workspace = str(body.get("workspace") or "INTRADAY").strip().upper()
    symbol = str(body.get("symbol") or "").strip().upper()
    option_type = str(body.get("option_type") or "").strip().upper()

    if workspace not in accounts.WORKSPACES:
        return _failure("UNKNOWN_WORKSPACE", "Choose INTRADAY, SWING or INVESTMENT capital.")
    if action in {"SELL", "SHORT", "SELL_TO_OPEN", "OPEN_SHORT"}:
        return _failure(
            "NAKED_SHORT_OPTION_BLOCKED",
            "Naked option selling is blocked. Only long CALL/PUT paper entries and closes are allowed.",
        )
    match = _OPTION_SYMBOL.fullmatch(symbol)
    if not match or option_type not in {"CE", "PE"} or match.group(2) != option_type:
        return _failure("INVALID_OPTION_CONTRACT", "Select an exact verified CE/PE contract first.")

    # Closing is risk-reducing and therefore does not require the entry scanner
    # to be running or ledger reconciliation to be clean. It still requires a
    # verified tradable exit quote; stale/closed-market fills are never invented.
    if action == "CLOSE":
        requested_id = body.get("position_id")
        positions = _open_positions(runtime, workspace)
        position = next(
            (
                item
                for item in positions
                if (requested_id is not None and str(item.get("id")) == str(requested_id))
                or (requested_id is None and str(item.get("symbol") or "").upper() == symbol)
            ),
            None,
        )
        if position is None:
            return _failure("OPTION_POSITION_NOT_FOUND", "No matching open paper option position exists.")
        certificate = _certificate(runtime, symbol)
        if not certificate.get("eligible_for_exit"):
            reason = str(certificate.get("reason") or "LIVE_EXIT_CERTIFICATE_REQUIRED")
            return _failure(reason, f"Paper close blocked: {reason.replace('_', ' ')}.", certificate=certificate)
        exit_price = _number(certificate.get("bid"), _number(certificate.get("mark")))
        if not exit_price or exit_price <= 0:
            return _failure("INVALID_EXIT_MARK", "A verified positive option exit price is required.")
        result = runtime.desk.close_position(
            position_id=int(position["id"]),
            exit_price=float(exit_price),
            reason="MANUAL_V16_OPTION_CLOSE",
        )
        return {
            **result,
            "action": "CLOSE_LONG_OPTION",
            "workspace": workspace,
            "symbol": symbol,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "live_orders_locked": True,
            "naked_option_selling": False,
        }

    if action != "BUY":
        return _failure("UNSUPPORTED_OPTION_ACTION", "Use BUY for a long option entry or CLOSE for an existing long option.")

    reconciliation = runtime.reconcile()
    if not reconciliation.get("success"):
        return _failure(
            "LEDGER_RECONCILIATION_REQUIRED",
            "Canonical ledger reconciliation must be clean before creating new exposure.",
            reconciliation=reconciliation,
        )
    session = accounts.session(runtime.desk, workspace)
    if session.get("state") != "RUNNING":
        return _failure(
            "WORKSPACE_PAUSED",
            f"Start the {workspace} paper session before opening a new option position.",
        )

    certificate = _certificate(runtime, symbol)
    if not certificate.get("eligible_for_entry"):
        reason = str(certificate.get("reason") or "LIVE_ENTRY_CERTIFICATE_REQUIRED")
        return _failure(
            reason,
            f"Paper entry blocked: {reason.replace('_', ' ')}. No stale or after-hours fill was created.",
            certificate=certificate,
        )

    try:
        spec = option_instrument_spec(symbol)
    except Exception as exc:
        return _failure("INSTRUMENT_SPEC_UNAVAILABLE", _safe_text(exc))

    entry = _number(certificate.get("ask"), _number(certificate.get("mark")))
    stop = _number(body.get("stop"))
    target = _number(body.get("target"))
    lots_value = _number(body.get("lots"), 1.0) or 1.0
    lots = int(lots_value)
    if not entry or entry <= 0:
        return _failure("INVALID_ENTRY", "A verified positive option entry quote is required.")
    if stop is None or target is None:
        return _failure(
            "MANUAL_RISK_LEVELS_REQUIRED",
            "Enter an explicit stop and target. JARVIS will not fabricate option risk levels.",
        )
    if not 0 < stop < entry < target:
        return _failure(
            "INVALID_RISK_LEVELS",
            f"For a long option require STOP < live entry ({entry:.2f}) < TARGET.",
        )
    if lots < 1 or lots > 100:
        return _failure("INVALID_QUANTITY", "Paper option quantity must be between 1 and 100 lots.")

    risk_reward = (target - entry) / (entry - stop) if entry > stop else None
    external_id = str(body.get("client_order_id") or "").strip()
    if not external_id:
        external_id = f"v16-opt:{workspace}:{symbol}:{int(time.time() * 1000)}"
    metadata = {
        "manual_paper": True,
        "manual_option_order": True,
        "underlying": str(body.get("underlying") or "").upper() or None,
        "option_type": option_type,
        "strike": _number(body.get("strike"), _number(spec.get("strike"))),
        "expiry": body.get("expiry") or spec.get("expiry"),
        "session_generation": session.get("generation"),
        "entry_certificate": certificate,
        "risk_reward": risk_reward,
        "requested_lots": lots,
        "live_execution": False,
        "automatic_broker_order": False,
    }
    result = runtime.desk.open_position(
        symbol=symbol,
        side="LONG",
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        quantity=float(lots),
        timeframe=str(body.get("timeframe") or "5m"),
        strategy="MANUAL_LONG_OPTION_V16",
        score=None,
        source="JARVIS_V16_OPTIONS_PAPER",
        asset_type="OPTION",
        external_id=external_id,
        metadata=metadata,
        risk_multiplier=0.25,
        valuation_multiplier=1.0,
        instrument_spec=spec,
        portfolio_bucket=workspace,
        bucket_allocation_fraction=float(session.get("allocation") or 1.0),
    )
    return {
        **result,
        "action": "BUY_LONG_CALL" if option_type == "CE" else "BUY_LONG_PUT",
        "workspace": workspace,
        "symbol": symbol,
        "option_type": option_type,
        "lots_requested": lots,
        "entry_reference": entry,
        "stop": stop,
        "target": target,
        "risk_reward": risk_reward,
        "instrument_spec": spec,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "live_orders_locked": True,
        "naked_option_selling": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def repair_legacy_links(desk: Any) -> dict[str, Any]:
    """Backfill only unambiguous missing links; never delete or rewrite trades."""
    repaired: list[str] = []
    skipped: list[str] = []
    with desk._lock, desk._connection() as conn:
        rows = list(conn.execute("SELECT * FROM paper_positions ORDER BY id"))
        for row in rows:
            position_id = int(row["id"])
            metadata = desk._metadata(row)
            open_event = conn.execute(
                "SELECT 1 FROM paper_events WHERE position_id=? AND event_type='OPEN' LIMIT 1",
                (position_id,),
            ).fetchone()
            if open_event is None:
                conn.execute(
                    "INSERT INTO paper_events(position_id,event_type,created_at,payload_json) VALUES(?,?,?,?)",
                    (
                        position_id,
                        "OPEN",
                        str(row["opened_at"] or datetime.now(timezone.utc).isoformat()),
                        json.dumps({"migration": "V16_LEGACY_LINK", "symbol": row["symbol"], "side": row["side"]}),
                    ),
                )
                repaired.append(f"OPEN_EVENT:{position_id}")
            if str(row["status"]) == "CLOSED":
                close_event = conn.execute(
                    "SELECT 1 FROM paper_events WHERE position_id=? AND event_type='CLOSE' LIMIT 1",
                    (position_id,),
                ).fetchone()
                if close_event is None:
                    conn.execute(
                        "INSERT INTO paper_events(position_id,event_type,created_at,payload_json) VALUES(?,?,?,?)",
                        (
                            position_id,
                            "CLOSE",
                            str(row["closed_at"] or datetime.now(timezone.utc).isoformat()),
                            json.dumps({
                                "migration": "V16_LEGACY_LINK",
                                "exit_price": row["exit_price"],
                                "reason": metadata.get("exit_reason") or "LEGACY_CLOSE",
                            }),
                        ),
                    )
                    repaired.append(f"CLOSE_EVENT:{position_id}")
            if metadata.get("workspace_sizing") is not None:
                filled = conn.execute(
                    "SELECT 1 FROM terminal_orders WHERE position_id=? AND status='FILLED' AND kind='ENTRY' LIMIT 1",
                    (position_id,),
                ).fetchone()
                if filled is None:
                    external_id = row["external_id"]
                    conflict = None
                    if external_id:
                        conflict = conn.execute(
                            "SELECT position_id FROM terminal_orders WHERE external_id=? AND status='FILLED' LIMIT 1",
                            (external_id,),
                        ).fetchone()
                    if conflict and int(conflict["position_id"] or 0) != position_id:
                        skipped.append(f"ORDER_KEY_CONFLICT:{position_id}")
                    else:
                        conn.execute(
                            "INSERT INTO terminal_orders(workspace,external_id,position_id,status,reason,created_at,payload_json,kind) VALUES(?,?,?,?,?,?,?,?)",
                            (
                                accounts.workspace(metadata.get("portfolio_bucket")),
                                external_id,
                                position_id,
                                "FILLED",
                                "V16_LEGACY_LINK_BACKFILL",
                                str(row["opened_at"] or datetime.now(timezone.utc).isoformat()),
                                json.dumps({"migration": "V16_LEGACY_LINK", "symbol": row["symbol"], "side": row["side"]}),
                                "ENTRY",
                            ),
                        )
                        repaired.append(f"ENTRY_ORDER:{position_id}")
    return {
        "success": not skipped,
        "repaired": repaired,
        "skipped": skipped,
        "paper_only": True,
        "live_execution": False,
    }
