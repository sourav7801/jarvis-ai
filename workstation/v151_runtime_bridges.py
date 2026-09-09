from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False


def install_v151_runtime_bridges() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()
        from workstation.v15_runtime_bridges import install_v15_runtime_bridges
        from workstation.options_runtime_v151 import status as options_status
        v15 = install_v15_runtime_bridges()
        options = options_status()
        _INSTALLED = bool(v15.get("installed") and options.get("success"))
        return {**status(), "v15": v15, "options": options}


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED
    try:
        from workstation.v15_runtime_bridges import status as v15_status
        v15 = v15_status()
    except Exception:
        v15 = {"installed": False, "v141_risk_geometry_installed": False}
    try:
        from workstation.options_runtime_v151 import status as options_status
        options = options_status()
    except Exception:
        options = {"success": False}
    return {
        "success": True,
        "version": "15.1",
        "service": "JARVIS_OPTIONS_EXECUTION_INTELLIGENCE_V15_1",
        "installed": installed,
        "v15_market_reasoning_preserved": v15.get("installed") is True,
        "v141_risk_geometry_preserved": v15.get("v141_risk_geometry_installed") is True,
        "options_intelligence_ready": options.get("success") is True,
        "read_only_chain_provider_preserved": True,
        "long_premium_only": True,
        "naked_option_selling": False,
        "verified_option_chain_required": True,
        "verified_instrument_spec_required": True,
        "paper_desk_final_authority": True,
        "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
        "permanent_agents": 29,
        "system_planes_do_not_count_as_agents": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    }


__all__ = ["install_v151_runtime_bridges", "status"]
