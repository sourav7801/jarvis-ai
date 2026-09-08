from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
_SIZING_INSTALLED = False


def install_v13_runtime_bridges() -> dict[str, Any]:
    """Install V13 paper-only contextual authority into canonical processes.

    V12 classes/endpoints stay intact for cross-generation compatibility. Their
    process-local policy globals are rebound to the V13 contextual engine so the
    active runtime uses contextual EV, outcome memory and dynamic correlation.

    V13 also installs constraint-aware automatic Paper Desk sizing before any
    paper engine starts. This fixes inherited floor-division behavior that could
    turn a valid fractional BTC/crypto quantity into zero and leave JARVIS in
    watching mode. Existing portfolio limits remain final authority.
    """

    global _INSTALLED, _SIZING_INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from omni.trading_intelligence.contextual_decision_engine_v13 import (
            CONTEXTUAL_DECISION_ENGINE_V13,
            DECISION_VERSION,
        )
        from workstation import adaptive_paper_autonomy_engine as adaptive_engine_module
        from workstation import adaptive_direct_trade_bridge as direct_bridge_module
        from workstation import adaptive_market_sampler as sampler_module
        from workstation.adaptive_discovery_router_v13 import install_adaptive_discovery_router_v13
        from workstation.paper_execution_sizing_v13 import install_v13_execution_sizing_bridge

        sizing = install_v13_execution_sizing_bridge()
        _SIZING_INSTALLED = bool(sizing.get("installed"))

        adaptive_engine_module.ADAPTIVE_OPPORTUNITY_POLICY = CONTEXTUAL_DECISION_ENGINE_V13
        adaptive_engine_module.POLICY_VERSION = DECISION_VERSION
        direct_bridge_module.ADAPTIVE_OPPORTUNITY_POLICY = CONTEXTUAL_DECISION_ENGINE_V13
        sampler_module.ADAPTIVE_OPPORTUNITY_POLICY = CONTEXTUAL_DECISION_ENGINE_V13

        discovery = install_adaptive_discovery_router_v13()
        _INSTALLED = True
        return {**status(), "discovery": discovery, "execution_sizing": sizing}


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED
        sizing_installed = _SIZING_INSTALLED
    return {
        "success": True,
        "version": "13.0",
        "installed": installed,
        "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
        "v12_base_policy_preserved": True,
        "adaptive_engine_rebound": installed,
        "direct_paper_command_rebound": installed,
        "market_sampler_rebound": installed,
        "continuous_top_n_discovery": installed,
        "fractional_auto_sizing_installed": sizing_installed,
        "constraint_aware_auto_sizing": sizing_installed,
        "static_67_68_70_execution_authority": False,
        "static_discovery_score_gate": False if installed else None,
        "contextual_outcome_memory": True,
        "dynamic_portfolio_correlation": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
    }


__all__ = ["install_v13_runtime_bridges", "status"]
