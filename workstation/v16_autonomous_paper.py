"""Canonical V16 autonomous PAPER option execution bridge.

The adaptive scanner already discovers and ranks opportunities.  This module
changes only the V16 option admission path: verified option plans are rechecked
against the canonical TerminalRuntime and then sized/opened by the existing
PaperTradingDesk.  It has no broker client and exposes no live-order method.

The legacy V15.1 adapter remains available outside the V16 professional runtime
for compatibility, but a V16 workstation installs this bridge over the same
singleton so there is still only one scanner and one Paper Desk authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Mapping


SAFETY = {
    "paper_only": True,
    "live_execution": False,
    "automatic_broker_order": False,
    "live_orders_locked": True,
    "naked_option_selling": False,
}
SUPPORTED_AUTO_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "SENSEX"}
AUTO_OPTION_WORKSPACES = {"INTRADAY", "SWING"}


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _failure(reason: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "reason": reason, "message": message, **SAFETY, **extra}


def _option_type(value: Any) -> str | None:
    token = str(value or "").strip().upper()
    if token in {"CE", "CALL"}:
        return "CE"
    if token in {"PE", "PUT"}:
        return "PE"
    return None


def _open_positions(runtime: Any, workspace: str) -> list[dict[str, Any]]:
    try:
        state = runtime.snapshot(workspace)
        return list((state.get("account") or {}).get("positions") or [])
    except Exception:
        return []


def _symbol_underlying(symbol: str) -> str | None:
    token = str(symbol or "").upper()
    # BANKNIFTY must be checked before NIFTY because its name contains NIFTY.
    if "BANKNIFTY" in token or "NIFTYBANK" in token:
        return "BANKNIFTY"
    if "SENSEX" in token:
        return "SENSEX"
    if "NIFTY" in token:
        return "NIFTY"
    return None


def _same_underlying_exposure(position: Mapping[str, Any], underlying: str) -> bool:
    metadata = position.get("metadata") if isinstance(position.get("metadata"), Mapping) else {}
    asset_type = str(position.get("asset_type") or metadata.get("asset_type") or "").upper()
    position_underlying = str(metadata.get("underlying") or "").upper()
    symbol = str(position.get("symbol") or "").upper()
    if position_underlying:
        return position_underlying == underlying
    # Older canonical option rows can predate the explicit underlying field.
    return bool(asset_type == "OPTION" and _symbol_underlying(symbol) == underlying)


def autonomous_option_plan(
    runtime: Any,
    plan: Mapping[str, Any],
    *,
    portfolio_bucket: str = "INTRADAY",
    bucket_allocation_fraction: float = 0.50,
    session_generation: int | None = None,
    signal_id: str | None = None,
) -> dict[str, Any]:
    """Admit one verified autonomous long-premium option plan to Paper Desk.

    Stop/target/contract selection come from verified option intelligence.  The
    final entry is always a fresh read-only quote, and quantity is deliberately
    ``None`` so PaperTradingDesk performs canonical risk/capital sizing.
    """
    payload = dict(plan or {})
    workspace = str(portfolio_bucket or "INTRADAY").upper()
    underlying = str(payload.get("underlying") or "").upper()
    selected = payload.get("selected") if isinstance(payload.get("selected"), Mapping) else {}
    risk_plan = selected.get("risk_plan") if isinstance(selected.get("risk_plan"), Mapping) else {}
    symbol = str(selected.get("symbol") or payload.get("selected_contract") or "").upper()
    option_type = _option_type(selected.get("option_type") or payload.get("desired_option_type"))

    if workspace not in AUTO_OPTION_WORKSPACES:
        return _failure(
            "AUTO_OPTIONS_WORKSPACE_UNSUPPORTED",
            "Autonomous long-option expression is enabled for INTRADAY and SWING only; INVESTMENT remains long-only cash/equity research.",
        )
    if underlying not in SUPPORTED_AUTO_UNDERLYINGS:
        return _failure("AUTO_OPTION_UNDERLYING_UNSUPPORTED", "Autonomous V16 options currently require NIFTY, BANKNIFTY or SENSEX.")
    if payload.get("executable") is not True:
        return _failure(str(payload.get("reason") or "OPTION_PLAN_NOT_EXECUTABLE"), "Verified option intelligence did not produce an executable long-premium plan.")
    if not symbol or option_type not in {"CE", "PE"}:
        return _failure("INVALID_OPTION_CONTRACT", "Autonomous option plan did not contain an exact CE/PE contract.")
    if not signal_id:
        return _failure("SIGNAL_BAR_ID_REQUIRED", "A completed-bar signal identity is required for idempotent autonomous execution.")

    reconciliation = runtime.reconcile()
    if not reconciliation.get("success"):
        return _failure(
            "LEDGER_RECONCILIATION_REQUIRED",
            "Canonical ledger reconciliation must be clean before creating new autonomous exposure.",
            reconciliation=reconciliation,
        )

    try:
        state = runtime.snapshot(workspace)
    except Exception as exc:
        return _failure("CANONICAL_STATE_UNAVAILABLE", f"Canonical workspace state unavailable: {type(exc).__name__}")
    if str(state.get("entry_session") or "").upper() != "RUNNING":
        return _failure("WORKSPACE_PAUSED", f"Start the {workspace} autonomous paper session before opening new exposure.")

    positions = list((state.get("account") or {}).get("positions") or [])
    if any(_same_underlying_exposure(position, underlying) for position in positions):
        return _failure(
            "UNDERLYING_OPTION_EXPOSURE_EXISTS",
            f"An open {underlying} option exposure already exists in {workspace}; duplicate autonomous expression is blocked.",
        )

    try:
        from workstation.v16_option_paper import option_instrument_spec

        spec = option_instrument_spec(symbol)
    except Exception as exc:
        return _failure("INSTRUMENT_SPEC_UNAVAILABLE", str(exc)[:400])
    if spec.get("verified") is not True or _option_type(spec.get("option_type")) != option_type:
        return _failure("OPTION_INSTRUMENT_SPEC_UNVERIFIED", "Exact option contract metadata could not be verified.")

    try:
        certificate = dict(runtime.mark_loader(symbol))
    except Exception as exc:
        return _failure("OPTION_MARK_UNAVAILABLE", f"Fresh option quote unavailable: {type(exc).__name__}")
    if not certificate.get("eligible_for_entry"):
        reason = str(certificate.get("reason") or "LIVE_ENTRY_CERTIFICATE_REQUIRED")
        return _failure(reason, f"Autonomous paper entry blocked: {reason.replace('_', ' ')}.", certificate=certificate)

    entry = _number(certificate.get("ask"), _number(certificate.get("mark")))
    stop = _number(risk_plan.get("stop"))
    target = _number(risk_plan.get("target"))
    if not entry or entry <= 0:
        return _failure("INVALID_ENTRY", "A verified positive option ask/mark is required.")
    if stop is None or target is None:
        return _failure("AUTO_RISK_PLAN_UNAVAILABLE", "Verified option intelligence did not produce stop and target geometry.")
    if not 0 < stop < entry < target:
        return _failure(
            "LIVE_OPTION_QUOTE_OUTSIDE_SETUP",
            f"Fresh option quote {entry:.2f} moved outside the verified autonomous risk plan; wait for the next completed-bar plan.",
            planned_entry=_number(risk_plan.get("entry")),
            stop=stop,
            target=target,
        )

    risk_multiplier = _number(selected.get("risk_multiplier"), _number(payload.get("risk_multiplier"), 0.0)) or 0.0
    risk_multiplier = max(0.0, min(risk_multiplier, 1.0))
    if risk_multiplier <= 0:
        return _failure("OPTION_RISK_MULTIPLIER_ZERO", "Autonomous option risk budget is zero after evidence/uncertainty adjustment.")

    external_id = f"v16-auto-option:{workspace}:{underlying}:{symbol}:{signal_id}"
    underlying_decision = payload.get("underlying_decision") if isinstance(payload.get("underlying_decision"), Mapping) else {}
    metadata = {
        "autonomous_paper": True,
        "manual_option_order": False,
        "v16_autonomous_option": True,
        "underlying": underlying,
        "option_type": option_type,
        "strike": selected.get("strike") or spec.get("strike"),
        "expiry": selected.get("expiry") or spec.get("expiry"),
        "session_generation": session_generation,
        "signal_id": str(signal_id),
        "entry_certificate": certificate,
        "option_expected_value_r": selected.get("option_expected_value_r") or payload.get("option_expected_value_r"),
        "option_utility": selected.get("option_utility") or payload.get("option_utility"),
        "underlying_decision": dict(underlying_decision),
        "premium_risk_plan": dict(risk_plan),
        "verified_greeks": {
            name: (selected.get("quote") or {}).get(name)
            for name in ("delta", "gamma", "theta", "vega")
        },
        "implied_volatility": (selected.get("quote") or {}).get("implied_volatility"),
        "auto_contract_selection": True,
        "auto_risk_geometry": True,
        "auto_position_sizing": True,
        "long_premium_only": True,
        "naked_option_selling": False,
        "live_execution": False,
        "automatic_broker_order": False,
    }
    result = runtime.desk.open_position(
        symbol=symbol,
        side="LONG",
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        quantity=None,
        timeframe="OPTIONS_AUTO",
        strategy="JARVIS_V16_AUTONOMOUS_OPTIONS",
        score=None,
        source="JARVIS_V16_AUTONOMOUS_PAPER",
        asset_type="OPTION",
        external_id=external_id,
        metadata=metadata,
        risk_multiplier=risk_multiplier,
        valuation_multiplier=1.0,
        instrument_spec=spec,
        portfolio_bucket=workspace,
        bucket_allocation_fraction=max(0.0, min(float(bucket_allocation_fraction), 1.0)),
    )
    return {
        **dict(result),
        "automation": True,
        "action": "AUTO_BUY_LONG_CALL" if option_type == "CE" else "AUTO_BUY_LONG_PUT",
        "workspace": workspace,
        "underlying": underlying,
        "symbol": symbol,
        "option_type": option_type,
        "entry_reference": entry,
        "stop": stop,
        "target": target,
        "risk_multiplier": risk_multiplier,
        "external_id": external_id,
        "auto_contract_selection": True,
        "auto_risk_geometry": True,
        "auto_position_sizing": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **SAFETY,
    }


@dataclass
class V16AutonomousOptionBridge:
    runtime: Any
    original_open_plan: Any

    def open_plan(self, plan: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
        desk = kwargs.get("desk")
        if desk is not None and desk is not self.runtime.desk:
            return self.original_open_plan(plan, **kwargs)
        return autonomous_option_plan(
            self.runtime,
            plan,
            portfolio_bucket=kwargs.get("portfolio_bucket", "INTRADAY"),
            bucket_allocation_fraction=kwargs.get("bucket_allocation_fraction", 0.50),
            session_generation=kwargs.get("session_generation"),
            signal_id=kwargs.get("signal_id"),
        )

    def status(self, workspace: str = "INTRADAY") -> dict[str, Any]:
        try:
            state = self.runtime.snapshot(workspace)
            entry_session = state.get("entry_session")
            scan = state.get("scan") or {}
        except Exception:
            entry_session, scan = None, {}
        return {
            "success": True,
            "service": "JARVIS_V16_AUTONOMOUS_PAPER",
            "installed": True,
            "workspace": workspace,
            "entry_session": entry_session,
            "scanner_running": bool(scan.get("scanning")),
            "auto_contract_selection": True,
            "auto_stop_target": True,
            "auto_position_sizing": True,
            "auto_position_management": True,
            "auto_journal": True,
            "option_underlyings": sorted(SUPPORTED_AUTO_UNDERLYINGS),
            "option_workspaces": sorted(AUTO_OPTION_WORKSPACES),
            "manual_ticket_required": False,
            **SAFETY,
        }


def install_v16_autonomous_option_bridge(runtime: Any) -> V16AutonomousOptionBridge:
    """Route the existing adaptive scanner's option plans into canonical V16."""
    from workstation.options_paper_execution_v151 import OPTIONS_PAPER_EXECUTION_V151

    existing = getattr(runtime, "v16_autonomy_service", None)
    if isinstance(existing, V16AutonomousOptionBridge):
        return existing
    original = OPTIONS_PAPER_EXECUTION_V151.open_plan
    bridge = V16AutonomousOptionBridge(runtime=runtime, original_open_plan=original)
    OPTIONS_PAPER_EXECUTION_V151.open_plan = bridge.open_plan
    runtime.v16_autonomy_service = bridge
    return bridge


__all__ = [
    "SAFETY",
    "SUPPORTED_AUTO_UNDERLYINGS",
    "AUTO_OPTION_WORKSPACES",
    "V16AutonomousOptionBridge",
    "autonomous_option_plan",
    "install_v16_autonomous_option_bridge",
]
