"""V13 constraint-aware automatic paper-position sizing.

The protected Paper Desk is still the final risk authority.  This bridge fixes a
specific automatic-sizing defect in the inherited desk: automatic quantity used
floor division before the instrument quantity step was applied.  That makes a
valid fractional crypto size such as 0.004 BTC become 0 and leaves JARVIS in
watching mode even after a PRIMARY/PROBE decision.

V13 computes a fractional quantity first, caps it by every existing portfolio
risk/exposure budget, then quantizes to the verified provider quantity step.  It
never increases an explicit user quantity, never relaxes a portfolio limit and
never exposes a broker order surface.
"""
from __future__ import annotations

import math
from threading import RLock
from typing import Any, Mapping

from workstation.paper_instrument_accounting import (
    normalized_price_grid,
    quantize_quantity,
    validate_instrument_spec,
)


_LOCK = RLock()
_INSTALLED = False
_ORIGINAL_OPEN_POSITION = None
SIZING_VERSION = "CONSTRAINT_AWARE_FRACTIONAL_PAPER_SIZING_V13"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _side(value: Any) -> str:
    token = str(value or "").strip().upper()
    if token in {"BUY", "LONG"}:
        return "LONG"
    if token in {"SELL", "SHORT"}:
        return "SHORT"
    return token


def _exposure(snapshot: Mapping[str, Any], group: str, key: str) -> float:
    table = snapshot.get(group) if isinstance(snapshot.get(group), Mapping) else {}
    normalized = str(key or "UNSPECIFIED").strip().upper() or "UNSPECIFIED"
    return max(0.0, _f(table.get(normalized)))


def _cap_from_available(available: float, per_unit: float) -> float:
    if per_unit <= 0:
        return 0.0
    return max(0.0, float(available)) / per_unit


def plan_auto_quantity(desk: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    """Return a quantity plan without mutating the Paper Desk.

    Score/EV does not size the position directly.  The decision engine supplies a
    bounded risk multiplier; this planner turns that budget into an instrument-
    valid quantity while respecting all existing desk exposure constraints.
    """

    symbol = str(request.get("symbol") or "").strip().upper()
    side = _side(request.get("side"))
    asset_type = str(request.get("asset_type") or "SPOT").strip().upper() or "SPOT"
    strategy = str(request.get("strategy") or "QUANT_ENSEMBLE")
    bucket = str(request.get("portfolio_bucket") or "GENERAL").strip().upper() or "GENERAL"
    bucket_fraction = max(0.01, min(_f(request.get("bucket_allocation_fraction"), 1.0), 1.0))
    entry = _f(request.get("entry"))
    stop_raw = request.get("stop")
    stop = _f(stop_raw) if stop_raw is not None else None
    target_raw = request.get("target")
    target = _f(target_raw) if target_raw is not None else None
    requested_risk_multiplier = max(0.0, min(_f(request.get("risk_multiplier"), 1.0), 1.0))
    valuation_multiplier = max(_f(request.get("valuation_multiplier"), 1.0), 0.000001)

    if not symbol or entry <= 0 or side not in {"LONG", "SHORT"}:
        return {
            "success": False,
            "version": SIZING_VERSION,
            "reason": "INVALID_ENTRY",
            "quantity": 0.0,
            "paper_only": True,
            "live_execution": False,
        }
    if stop is None:
        return {
            "success": False,
            "version": SIZING_VERSION,
            "reason": "STOP_REQUIRED_FOR_SIZING",
            "quantity": 0.0,
            "paper_only": True,
            "live_execution": False,
        }

    spec, spec_error = validate_instrument_spec(
        request.get("instrument_spec") if isinstance(request.get("instrument_spec"), dict) else None,
        asset_type=asset_type,
    )
    if spec_error:
        return {
            "success": False,
            "version": SIZING_VERSION,
            "reason": spec_error,
            "quantity": 0.0,
            "paper_only": True,
            "live_execution": False,
        }

    quantity_step = spec.quantity_step if spec is not None else 1.0
    contract_multiplier = spec.contract_multiplier if spec is not None else 1.0
    entry, stop, target = normalized_price_grid(
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        tick_size=spec.tick_size if spec is not None else None,
    )
    if stop is None:
        return {
            "success": False,
            "version": SIZING_VERSION,
            "reason": "STOP_REQUIRED_FOR_SIZING",
            "quantity": 0.0,
            "paper_only": True,
            "live_execution": False,
        }

    position_multiplier = valuation_multiplier * max(contract_multiplier, 0.000001)
    per_unit_risk = abs(entry - stop) * position_multiplier
    per_unit_notional = abs(entry) * position_multiplier
    if per_unit_risk <= 0 or per_unit_notional <= 0 or requested_risk_multiplier <= 0:
        return {
            "success": False,
            "version": SIZING_VERSION,
            "reason": "POSITION_SIZE_ZERO",
            "quantity": 0.0,
            "paper_only": True,
            "live_execution": False,
        }

    snapshot = desk.snapshot()
    equity = max(_f(snapshot.get("equity")), 0.0)
    risk_budget = equity * max(_f(getattr(desk, "max_single_risk_fraction", 0.01)), 0.0) * requested_risk_multiplier

    caps: list[dict[str, Any]] = []

    def add_cap(name: str, quantity_cap: float, *, available: float | None = None) -> None:
        caps.append({
            "name": name,
            "quantity_cap": max(0.0, float(quantity_cap)),
            "available": None if available is None else max(0.0, float(available)),
        })

    add_cap("SINGLE_TRADE_RISK_BUDGET", _cap_from_available(risk_budget, per_unit_risk), available=risk_budget)

    total_risk_limit = equity * max(_f(getattr(desk, "max_total_risk_fraction", 0.04)), 0.0)
    total_risk_available = max(0.0, total_risk_limit - _f(snapshot.get("risk_at_stops")))
    add_cap("PORTFOLIO_RISK_LIMIT", _cap_from_available(total_risk_available, per_unit_risk), available=total_risk_available)

    bucket_risk_table = snapshot.get("bucket_risk_at_stops") if isinstance(snapshot.get("bucket_risk_at_stops"), Mapping) else {}
    bucket_risk_limit = total_risk_limit * bucket_fraction
    bucket_risk_available = max(0.0, bucket_risk_limit - _f(bucket_risk_table.get(bucket)))
    add_cap("BUCKET_RISK_LIMIT", _cap_from_available(bucket_risk_available, per_unit_risk), available=bucket_risk_available)

    gross_limit = equity * max(_f(getattr(desk, "max_gross_exposure_multiple", 2.0)), 0.0)
    gross_available = max(0.0, gross_limit - _f(snapshot.get("gross_exposure")))
    add_cap("GROSS_EXPOSURE_LIMIT", _cap_from_available(gross_available, per_unit_notional), available=gross_available)

    bucket_exposure_table = snapshot.get("bucket_exposure") if isinstance(snapshot.get("bucket_exposure"), Mapping) else {}
    bucket_notional_limit = gross_limit * bucket_fraction
    bucket_notional_available = max(0.0, bucket_notional_limit - _f(bucket_exposure_table.get(bucket)))
    add_cap("BUCKET_EXPOSURE_LIMIT", _cap_from_available(bucket_notional_available, per_unit_notional), available=bucket_notional_available)

    normalized_asset = asset_type or "SPOT"
    exposure_limits = (
        ("MAX_SYMBOL_EXPOSURE", "symbol_exposure", symbol, _f(getattr(desk, "max_symbol_exposure_fraction", 0.0))),
        ("MAX_ASSET_CLASS_EXPOSURE", "asset_class_exposure", normalized_asset, _f(getattr(desk, "max_asset_class_exposure_fraction", 0.0))),
        ("MAX_STRATEGY_EXPOSURE", "strategy_exposure", strategy, _f(getattr(desk, "max_strategy_exposure_fraction", 0.0))),
        ("MAX_DIRECTION_EXPOSURE", "direction_exposure", side, _f(getattr(desk, "max_direction_exposure_fraction", 0.0))),
    )
    for name, group, key, fraction in exposure_limits:
        if equity <= 0 or fraction <= 0:
            continue
        limit = equity * fraction
        available = max(0.0, limit - _exposure(snapshot, group, key))
        add_cap(name, _cap_from_available(available, per_unit_notional), available=available)

    clusters = getattr(desk, "correlation_clusters", {}) or {}
    cluster = str(clusters.get(symbol) or "").strip().upper()
    cluster_fraction = _f(getattr(desk, "max_correlated_exposure_fraction", 0.0))
    if cluster and equity > 0 and cluster_fraction > 0:
        limit = equity * cluster_fraction
        available = max(0.0, limit - _exposure(snapshot, "correlation_cluster_exposure", cluster))
        add_cap("MAX_CORRELATED_EXPOSURE", _cap_from_available(available, per_unit_notional), available=available)

    limiting = min(caps, key=lambda item: item["quantity_cap"]) if caps else {
        "name": "NO_CAP",
        "quantity_cap": 0.0,
        "available": None,
    }
    raw_quantity = max(0.0, _f(limiting.get("quantity_cap")))
    quantity = quantize_quantity(raw_quantity, quantity_step)
    planned_risk = quantity * per_unit_risk
    planned_notional = quantity * per_unit_notional

    if quantity <= 0:
        return {
            "success": False,
            "version": SIZING_VERSION,
            "reason": "POSITION_SIZE_ZERO",
            "sizing_reason": "AUTO_SIZE_BELOW_VERIFIED_MINIMUM_STEP",
            "limiting_constraint": limiting.get("name"),
            "quantity": 0.0,
            "raw_quantity": raw_quantity,
            "quantity_step": quantity_step,
            "requested_risk_multiplier": requested_risk_multiplier,
            "risk_budget": risk_budget,
            "per_unit_risk": per_unit_risk,
            "per_unit_notional": per_unit_notional,
            "constraints": caps,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    return {
        "success": True,
        "version": SIZING_VERSION,
        "reason": "AUTO_QUANTITY_PLANNED",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "raw_quantity": raw_quantity,
        "quantity_step": quantity_step,
        "requested_risk_multiplier": requested_risk_multiplier,
        "risk_budget": risk_budget,
        "planned_trade_risk": planned_risk,
        "planned_notional": planned_notional,
        "per_unit_risk": per_unit_risk,
        "per_unit_notional": per_unit_notional,
        "limiting_constraint": limiting.get("name"),
        "constraints": caps,
        "fractional_quantity_supported": quantity_step < 1.0,
        "constraint_aware": True,
        "risk_limits_relaxed": False,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def install_v13_execution_sizing_bridge() -> dict[str, Any]:
    """Patch automatic sizing only; explicit quantities keep protected behavior."""

    global _INSTALLED, _ORIGINAL_OPEN_POSITION
    with _LOCK:
        from workstation.paper_trading_desk import PaperTradingDesk

        if getattr(PaperTradingDesk.open_position, "_jarvis_v13_constraint_sizing", False):
            _INSTALLED = True
            return status()

        original = PaperTradingDesk.open_position
        _ORIGINAL_OPEN_POSITION = original

        def governed_open_position(self, *args, **kwargs):
            # The protected method is keyword-only. Positional callers are
            # delegated unchanged rather than reinterpreted by this bridge.
            if args or kwargs.get("quantity") is not None:
                return original(self, *args, **kwargs)

            plan = plan_auto_quantity(self, kwargs)
            if not plan.get("success"):
                return {
                    "success": False,
                    "reason": plan.get("reason") or "POSITION_SIZE_ZERO",
                    "sizing": plan,
                    "paper_only": True,
                    "live_execution": False,
                }

            call = dict(kwargs)
            call["quantity"] = float(plan["quantity"])
            metadata = dict(call.get("metadata") or {})
            metadata["v13_auto_sizing"] = dict(plan)
            metadata["requested_risk_multiplier"] = plan.get("requested_risk_multiplier")
            call["metadata"] = metadata
            result = dict(original(self, **call))
            result["sizing"] = dict(plan)
            result["requested_risk_multiplier"] = plan.get("requested_risk_multiplier")
            result["fractional_auto_sizing"] = bool(plan.get("fractional_quantity_supported"))
            result["constraint_aware_auto_sizing"] = True
            result["paper_only"] = True
            result["live_execution"] = False
            return result

        governed_open_position._jarvis_v13_constraint_sizing = True
        governed_open_position._jarvis_v13_original = original
        PaperTradingDesk.open_position = governed_open_position
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED
    return {
        "success": True,
        "version": "13.0",
        "service": SIZING_VERSION,
        "installed": installed,
        "fixes_fractional_floor_division": True,
        "fractional_crypto_auto_sizing": True,
        "constraint_aware_auto_sizing": True,
        "explicit_quantity_behavior_preserved": True,
        "risk_limits_relaxed": False,
        "paper_desk_final_risk_authority": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = [
    "SIZING_VERSION",
    "install_v13_execution_sizing_bridge",
    "plan_auto_quantity",
    "status",
]
