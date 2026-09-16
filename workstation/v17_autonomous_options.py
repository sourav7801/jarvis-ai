"""JARVIS V17 autonomous options convergence layer.

V17 does not create a second trading engine. It installs the verified V16
long-premium PAPER bridge over the canonical scanner/Paper Desk and exposes one
capability/status surface for the professional runtime.

Important invariants:
- market/chart intelligence comes from provider data, never screen pixels;
- the scanner may inspect many markets/timeframes, but no trade quota exists;
- only an exact provider-verified option contract can reach Paper Desk;
- live broker order placement is deliberately absent and remains locked;
- unsupported option venues fail closed instead of fabricating a contract;
- the durable V17 options-capital mandate is enforced at this final V17 bridge.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from workstation.v16_autonomous_paper import (
    AUTO_OPTION_WORKSPACES,
    SUPPORTED_AUTO_UNDERLYINGS,
    install_v16_autonomous_option_bridge,
)
from workstation.v17_autopilot_preferences import load_preferences


SAFETY = {
    "paper_only": True,
    "live_execution": False,
    "automatic_broker_order": False,
    "live_orders_locked": True,
    "naked_option_selling": False,
    "forced_trade_quota": False,
}

OPTION_EXECUTION_CAPABILITIES: dict[str, dict[str, Any]] = {
    "NIFTY": {
        "venue": "NSE",
        "auto_paper": True,
        "expression": "LONG_PREMIUM_CE_PE",
        "contract_source": "FYERS_NSE_FO_SYMBOL_MASTER",
    },
    "BANKNIFTY": {
        "venue": "NSE",
        "auto_paper": True,
        "expression": "LONG_PREMIUM_CE_PE",
        "contract_source": "FYERS_NSE_FO_SYMBOL_MASTER",
    },
    "SENSEX": {
        "venue": "BSE",
        "auto_paper": True,
        "expression": "LONG_PREMIUM_CE_PE",
        "contract_source": "FYERS_BSE_FO_SYMBOL_MASTER",
    },
    "MCX_OPTIONS": {
        "venue": "MCX",
        "auto_paper": False,
        "reason": "EXACT_MCX_OPTION_CONTRACT_RESOLVER_NOT_YET_VERIFIED",
    },
    "CRYPTO_OPTIONS": {
        "venue": "CRYPTO",
        "auto_paper": False,
        "reason": "VERIFIED_CRYPTO_OPTION_PROVIDER_NOT_YET_CONNECTED",
    },
}


def option_execution_capability(underlying: str) -> dict[str, Any]:
    """Return the fail-closed option execution capability for an underlying."""
    key = str(underlying or "").strip().upper()
    capability = OPTION_EXECUTION_CAPABILITIES.get(key)
    if capability is None:
        return {
            "underlying": key,
            "auto_paper": False,
            "reason": "OPTION_EXECUTION_CAPABILITY_UNVERIFIED",
            **SAFETY,
        }
    return {"underlying": key, **capability, **SAFETY}


def _v17_options_fraction() -> float:
    """Return the persisted V17 mandate without using current portfolio equity."""
    value = load_preferences().get("options_capital_fraction", 0.50)
    try:
        fraction = float(value)
    except (TypeError, ValueError):
        fraction = 0.50
    return max(0.05, min(fraction, 1.0))


@dataclass
class V17AutonomousOptionsRuntime:
    """One V17 facade around the already-canonical V16 execution authority."""

    runtime: Any
    v16_bridge: Any

    def open_plan(self, plan: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
        underlying = str((plan or {}).get("underlying") or "").strip().upper()
        capability = option_execution_capability(underlying)
        if not capability.get("auto_paper"):
            return {
                "success": False,
                "reason": capability.get("reason") or "OPTION_EXECUTION_CAPABILITY_UNVERIFIED",
                "message": (
                    f"{underlying or 'UNKNOWN'} may be scanned/researched, but autonomous option "
                    "paper execution is blocked until an exact verified contract provider is connected."
                ),
                "capability": capability,
                **SAFETY,
            }

        options_fraction = _v17_options_fraction()
        delegated = dict(kwargs)
        delegated["bucket_allocation_fraction"] = options_fraction
        result = dict(self.v16_bridge.open_plan(plan, **delegated))
        result.setdefault("v17_autonomous_options", True)
        result.setdefault("selection_mode", "AUTOMATIC_VERIFIED_CONTRACT")
        result.setdefault("manual_option_selection_required", False)
        result["options_capital_fraction"] = options_fraction
        result["daily_rebalance"] = False
        result["cross_workspace_top_up"] = False
        result.update(SAFETY)
        return result

    def status(self, workspace: str = "INTRADAY") -> dict[str, Any]:
        base = dict(self.v16_bridge.status(workspace))
        preferences = load_preferences()
        base.update(
            {
                "service": "JARVIS_V17_AUTONOMOUS_OPTIONS",
                "version": "17",
                "installed": True,
                "continuous_market_scanning": True,
                "decision_source": "LIVE_PROVIDER_DATA_AND_COMPLETED_BARS",
                "manual_option_selection_required": False,
                "automatic_contract_selection": True,
                "automatic_risk_sizing": True,
                "automatic_stop_target_management": True,
                "automatic_journal": True,
                "verified_auto_option_underlyings": sorted(SUPPORTED_AUTO_UNDERLYINGS),
                "auto_option_workspaces": sorted(AUTO_OPTION_WORKSPACES),
                "capabilities": OPTION_EXECUTION_CAPABILITIES,
                "trade_frequency_policy": "QUALITY_GATED_NO_FORCED_DAILY_QUOTA",
                "options_capital_fraction": preferences["options_capital_fraction"],
                "daily_rebalance": False,
                "cross_workspace_top_up": False,
                "learning_enabled": bool(preferences.get("learning_enabled", True)),
                "production_code_rewrite": False,
                **SAFETY,
            }
        )
        return base


def install_v17_autonomous_options(runtime: Any) -> V17AutonomousOptionsRuntime:
    """Install V17 without creating duplicate scanners or execution desks."""
    existing = getattr(runtime, "v17_autonomy_service", None)
    if isinstance(existing, V17AutonomousOptionsRuntime):
        return existing

    v16_bridge = install_v16_autonomous_option_bridge(runtime)
    service = V17AutonomousOptionsRuntime(runtime=runtime, v16_bridge=v16_bridge)

    from workstation.options_paper_execution_v151 import OPTIONS_PAPER_EXECUTION_V151

    OPTIONS_PAPER_EXECUTION_V151.open_plan = service.open_plan
    runtime.v17_autonomy_service = service
    return service


__all__ = [
    "SAFETY",
    "OPTION_EXECUTION_CAPABILITIES",
    "V17AutonomousOptionsRuntime",
    "install_v17_autonomous_options",
    "option_execution_capability",
    "_v17_options_fraction",
]
