"""Read-only preflight for V16 long-option paper entries.

This module does not create, modify, or close positions. It explains why the
canonical Paper Desk would currently admit or reject a long CE/PE paper entry.
The final order path re-runs all gates, so preflight can never authorize a stale
or unsafe fill by itself.
"""
from __future__ import annotations

import math
import re
from typing import Any

from workstation import workspace_accounts as accounts
from workstation.v16_option_paper import option_instrument_spec


_OPTION_SYMBOL = re.compile(r"^(NSE|BSE):[A-Z0-9._-]+(CE|PE)$")


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _result(success: bool, reason: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "success": bool(success),
        "ready": bool(success),
        "reason": reason,
        "message": message,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "live_orders_locked": True,
        "naked_option_selling": False,
        **extra,
    }


def option_preflight(runtime: Any, body: dict[str, Any]) -> dict[str, Any]:
    workspace = str(body.get("workspace") or "INTRADAY").strip().upper()
    symbol = str(body.get("symbol") or "").strip().upper()
    option_type = str(body.get("option_type") or "").strip().upper()

    if workspace not in accounts.WORKSPACES:
        return _result(False, "UNKNOWN_WORKSPACE", "Choose INTRADAY, SWING or INVESTMENT capital.")

    match = _OPTION_SYMBOL.fullmatch(symbol)
    if not match or option_type not in {"CE", "PE"} or match.group(2) != option_type:
        return _result(False, "INVALID_OPTION_CONTRACT", "Select an exact verified CE/PE contract first.")

    reconciliation = runtime.reconcile()
    if not reconciliation.get("success"):
        return _result(
            False,
            "LEDGER_RECONCILIATION_REQUIRED",
            "Canonical ledger reconciliation must be clean before creating new exposure.",
            reconciliation=reconciliation,
        )

    session = accounts.session(runtime.desk, workspace)
    if session.get("state") != "RUNNING":
        return _result(
            False,
            "WORKSPACE_PAUSED",
            f"Start the {workspace} paper session before opening a new option position.",
            session=session,
        )

    try:
        spec = option_instrument_spec(symbol)
    except Exception as exc:
        return _result(False, "INSTRUMENT_SPEC_UNAVAILABLE", str(exc)[:400], session=session)

    certificate = runtime.mark_loader(symbol)
    if not isinstance(certificate, dict):
        return _result(False, "DATA_UNAVAILABLE", "Verified option quote is unavailable.", session=session, instrument_spec=spec)
    if not certificate.get("eligible_for_entry"):
        reason = str(certificate.get("reason") or "LIVE_ENTRY_CERTIFICATE_REQUIRED")
        return _result(
            False,
            reason,
            f"Paper entry blocked: {reason.replace('_', ' ')}.",
            session=session,
            certificate=certificate,
            instrument_spec=spec,
        )

    entry = _number(certificate.get("ask"), _number(certificate.get("mark")))
    if not entry or entry <= 0:
        return _result(
            False,
            "INVALID_ENTRY",
            "Verified option quote did not contain a positive entry price.",
            session=session,
            certificate=certificate,
            instrument_spec=spec,
        )

    return _result(
        True,
        "PAPER_OPTION_READY",
        "Canonical ledger, paper session, contract metadata and live entry quote are ready.",
        workspace=workspace,
        symbol=symbol,
        option_type=option_type,
        entry_reference=entry,
        bid=_number(certificate.get("bid")),
        ask=_number(certificate.get("ask")),
        mark=_number(certificate.get("mark")),
        session=session,
        certificate=certificate,
        instrument_spec=spec,
    )


__all__ = ["option_preflight"]
