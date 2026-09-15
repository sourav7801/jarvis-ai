"""Server-authoritative V16 option execution readiness preview.

The preview is deliberately PAPER-only and read-only. It reuses the same strict
quote certificate, FYERS instrument specification and workspace admission logic
used by canonical Paper Desk execution. It never places an order and rolls back
the small daily-equity bookkeeping writes performed while sizing a preview.
"""
from __future__ import annotations

import math
from typing import Any

from workstation import workspace_accounts as accounts
from workstation.v16_option_paper import (
    _OPTION_SYMBOL,
    _certificate,
    _number,
    _safe_text,
    option_instrument_spec,
)


MAX_QUOTE_AGE_SECONDS = 30.0


def _safety(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "paper_only": True,
        "execution_mode": "PAPER",
        "live_execution": False,
        "automatic_broker_order": False,
        "live_orders_locked": True,
        "naked_option_selling": False,
    }


_MESSAGES = {
    "LIVE_EXECUTION_LOCKED": "Live option execution is locked; this terminal preview is PAPER-only.",
    "UNKNOWN_WORKSPACE": "Choose INTRADAY, SWING or INVESTMENT paper capital.",
    "INVALID_OPTION_CONTRACT": "Select an exact verified NSE/BSE CE or PE option contract.",
    "LEDGER_RECONCILIATION_REQUIRED": "Canonical ledger reconciliation must be clean before new exposure.",
    "WORKSPACE_PAUSED": "Start the selected paper workspace session before opening exposure.",
    "MANUAL_RISK_LEVELS_REQUIRED": "Enter an explicit stop and target; JARVIS will not fabricate risk levels.",
    "INVALID_ENTRY": "A verified positive option entry quote is required.",
    "INVALID_RISK_LEVELS": "For a long option require STOP < authoritative live entry < TARGET.",
    "INVALID_QUANTITY": "Paper option quantity must be a whole number between 1 and 100 lots.",
    "INSTRUMENT_SPEC_UNAVAILABLE": "The exact provider-verified option specification is unavailable.",
    "REQUEST_EXCEEDS_RISK_ADMISSION": "Requested lots exceed the canonical risk/capital admission. Use the safe lot count shown.",
}


def _block(code: str, detail: str | None = None) -> dict[str, str]:
    token = str(code or "EXECUTION_BLOCKED")
    return {
        "code": token,
        "message": detail or _MESSAGES.get(token, token.replace("_", " ").title()),
    }


def _requested_lots(params: dict[str, Any]) -> int | None:
    """Mirror canonical option-order lot semantics without coercing booleans.

    The execution path defaults an omitted lot field to one lot. A present but
    empty/invalid value is rejected. Keeping readiness and execution identical
    prevents the browser from displaying READY for a ticket the Paper Desk will
    later reject (or vice versa).
    """
    raw = params["lots"] if "lots" in params else 1
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not value.is_integer():
        return None
    lots = int(value)
    return lots if 1 <= lots <= 100 else None


def _quote_view(certificate: dict[str, Any]) -> dict[str, Any]:
    age = _number(certificate.get("age_seconds"))
    return {
        "mark": _number(certificate.get("mark")),
        "bid": _number(certificate.get("bid")),
        "ask": _number(certificate.get("ask")),
        "age_seconds": age,
        "max_age_seconds": MAX_QUOTE_AGE_SECONDS,
        "stale": bool(certificate.get("stale")),
        "verified": bool(certificate.get("verified")),
        "eligible_for_entry": bool(certificate.get("eligible_for_entry")),
        "source": certificate.get("source") or certificate.get("provider"),
        "received_at": certificate.get("received_at"),
        "exchange_timestamp": certificate.get("exchange_timestamp"),
        "session": certificate.get("session"),
        "reason": certificate.get("reason"),
    }


def _response(
    *,
    workspace: str,
    symbol: str,
    option_type: str,
    certificate: dict[str, Any] | None = None,
    reconciliation: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
    requested_lots: int | None = None,
    sizing: dict[str, Any] | None = None,
    blockers: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    blocks = list(blockers or [])
    admitted = _number((sizing or {}).get("quantity"))
    recommended = int(admitted) if admitted is not None and admitted >= 1 and float(admitted).is_integer() else admitted
    return _safety(
        {
            "success": True,
            "execution_ready": not blocks,
            "reason": blocks[0]["code"] if blocks else None,
            "block_reasons": blocks,
            "workspace": workspace,
            "symbol": symbol,
            "option_type": option_type,
            "quote": _quote_view(certificate or {}),
            "reconciliation": {
                "success": bool((reconciliation or {}).get("success")),
                "issue_count": int((reconciliation or {}).get("issue_count") or 0),
            },
            "session": {
                "state": str((session or {}).get("state") or "UNKNOWN").upper(),
                "generation": (session or {}).get("generation"),
            },
            "risk": {
                "requested_lots": requested_lots,
                "recommended_lots": recommended,
                "capital_allocated": _number((sizing or {}).get("capital_allocated")),
                "capital_at_risk": _number((sizing or {}).get("capital_at_risk")),
                "risk_budget": _number((sizing or {}).get("risk_budget")),
                "available_capital_before": _number((sizing or {}).get("available_capital_before")),
                "limiting_constraint": (sizing or {}).get("limiting_constraint"),
                "quantity_caps": dict((sizing or {}).get("quantity_caps") or {}),
                "quantity_step": _number((sizing or {}).get("quantity_step")),
                "contract_multiplier": _number((sizing or {}).get("contract_multiplier")),
                "cost_status": (sizing or {}).get("cost_status"),
            },
        }
    )


def option_readiness(runtime: Any, params: dict[str, Any]) -> dict[str, Any]:
    """Return a fail-closed, read-only preview for one manual long option order."""
    workspace = str(params.get("workspace") or "INTRADAY").strip().upper()
    symbol = str(params.get("symbol") or "").strip().upper()
    option_type = str(params.get("option_type") or "").strip().upper()
    requested_mode = str(params.get("execution_mode") or "PAPER").strip().upper()

    blockers: list[dict[str, str]] = []
    if requested_mode != "PAPER":
        blockers.append(_block("LIVE_EXECUTION_LOCKED"))
    if workspace not in accounts.WORKSPACES:
        blockers.append(_block("UNKNOWN_WORKSPACE"))

    match = _OPTION_SYMBOL.fullmatch(symbol)
    if not match or option_type not in {"CE", "PE"} or match.group(2) != option_type:
        blockers.append(_block("INVALID_OPTION_CONTRACT"))

    requested_lots = _requested_lots(params)
    if requested_lots is None:
        blockers.append(_block("INVALID_QUANTITY"))

    stop = _number(params.get("stop"))
    target = _number(params.get("target"))
    if stop is None or target is None:
        blockers.append(_block("MANUAL_RISK_LEVELS_REQUIRED"))
    elif not (0 < stop < target):
        blockers.append(_block("INVALID_RISK_LEVELS"))

    # Ticket-shape failures are deterministic. Do not hit the ledger, session,
    # quote provider or symbol master while the user is still editing an invalid
    # ticket. This also keeps the 4-second browser readiness poll inexpensive.
    if blockers:
        return _response(
            workspace=workspace,
            symbol=symbol,
            option_type=option_type,
            requested_lots=requested_lots,
            blockers=blockers,
        )

    reconciliation = runtime.reconcile()
    session = accounts.session(runtime.desk, workspace)
    certificate = _certificate(runtime, symbol)

    if not reconciliation.get("success"):
        blockers.append(_block("LEDGER_RECONCILIATION_REQUIRED"))
    if str(session.get("state") or "").upper() != "RUNNING":
        blockers.append(_block("WORKSPACE_PAUSED"))
    if not certificate.get("eligible_for_entry"):
        quote_reason = str(certificate.get("reason") or "LIVE_ENTRY_CERTIFICATE_REQUIRED")
        blockers.append(_block(quote_reason, f"Authoritative option quote blocked entry: {quote_reason.replace('_', ' ')}."))

    entry = _number(certificate.get("ask"), _number(certificate.get("mark")))
    if entry is None or entry <= 0:
        blockers.append(_block("INVALID_ENTRY"))
    elif not (0 < stop < entry < target):
        blockers.append(_block("INVALID_RISK_LEVELS"))

    if blockers:
        return _response(
            workspace=workspace,
            symbol=symbol,
            option_type=option_type,
            certificate=certificate,
            reconciliation=reconciliation,
            session=session,
            requested_lots=requested_lots,
            blockers=blockers,
        )

    try:
        spec = option_instrument_spec(symbol)
    except Exception as exc:
        blockers.append(_block("INSTRUMENT_SPEC_UNAVAILABLE", _safe_text(exc)))
        return _response(
            workspace=workspace,
            symbol=symbol,
            option_type=option_type,
            certificate=certificate,
            reconciliation=reconciliation,
            session=session,
            requested_lots=requested_lots,
            blockers=blockers,
        )

    request = {
        "symbol": symbol,
        "side": "LONG",
        "entry": float(entry),
        "stop": float(stop),
        "target": float(target),
        "quantity": float(requested_lots),
        "risk_multiplier": 0.25,
        "valuation_multiplier": 1.0,
        "instrument_spec": spec,
        "portfolio_bucket": workspace,
        "metadata": {
            "manual_paper": True,
            "manual_option_order": True,
            "underlying": str(params.get("underlying") or "").strip().upper() or None,
            "option_type": option_type,
            "strike": _number(params.get("strike"), _number(spec.get("strike"))),
            "expiry": params.get("expiry") or spec.get("expiry"),
            "session_generation": session.get("generation"),
            "entry_certificate": certificate,
            "requested_lots": requested_lots,
            "live_execution": False,
            "automatic_broker_order": False,
        },
    }

    # plan_admission updates persisted daily-equity bookkeeping while it sizes.
    # A readiness GET must not mutate terminal state, so perform the calculation
    # inside a SAVEPOINT and always roll it back. The Paper Desk lock prevents a
    # concurrent order from sharing this connection window.
    with runtime.desk._lock, runtime.desk._connection() as conn:
        conn.execute("SAVEPOINT v16_option_readiness")
        try:
            _planned_request, admission = accounts.plan_admission(runtime.desk, conn, request)
        finally:
            conn.execute("ROLLBACK TO v16_option_readiness")
            conn.execute("RELEASE v16_option_readiness")

    if not admission.get("success"):
        blockers.append(_block(str(admission.get("reason") or "RISK_ADMISSION_BLOCKED")))
        return _response(
            workspace=workspace,
            symbol=symbol,
            option_type=option_type,
            certificate=certificate,
            reconciliation=reconciliation,
            session=session,
            requested_lots=requested_lots,
            blockers=blockers,
        )

    sizing = dict(admission.get("sizing") or {})
    admitted = _number(sizing.get("quantity"), 0.0) or 0.0
    if abs(admitted - float(requested_lots)) > 1e-9:
        blockers.append(_block("REQUEST_EXCEEDS_RISK_ADMISSION"))

    return _response(
        workspace=workspace,
        symbol=symbol,
        option_type=option_type,
        certificate=certificate,
        reconciliation=reconciliation,
        session=session,
        requested_lots=requested_lots,
        sizing=sizing,
        blockers=blockers,
    )


__all__ = ["MAX_QUOTE_AGE_SECONDS", "option_readiness"]
