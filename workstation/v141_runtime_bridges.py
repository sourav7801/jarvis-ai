from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
_SCAN_WRAPPER_INSTALLED = False


def _install_scan_wrapper() -> dict[str, Any]:
    global _SCAN_WRAPPER_INSTALLED

    from workstation import quant_terminal_v2 as quant
    from workstation.risk_geometry_v141 import enrich_scan_row

    current = quant.scan_payload
    if getattr(current, "_jarvis_v141_risk_geometry", False):
        _SCAN_WRAPPER_INSTALLED = True
        return {"success": True, "installed": True}

    original = current

    def scan_payload_v141(symbol: str, profile: str = "intraday"):
        payload = original(symbol, profile=profile)
        if not isinstance(payload, dict):
            return payload
        return enrich_scan_row(payload)

    scan_payload_v141._jarvis_v141_risk_geometry = True
    scan_payload_v141._jarvis_v141_original = original
    quant.scan_payload = scan_payload_v141
    _SCAN_WRAPPER_INSTALLED = True
    return {"success": True, "installed": True}


def install_v141_runtime_bridges() -> dict[str, Any]:
    """Install verified risk-geometry reconstruction before V14 policy evaluation.

    V14 remains final execution authority. V14.1 only repairs the upstream
    contract which previously allowed legacy qualification to suppress valid
    entry/stop/target geometry. INVALID_RISK_LEVELS remains a hard blocker when
    verified completed-bar evidence is insufficient to derive geometry.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation.v14_runtime_bridges import install_v14_runtime_bridges

        v14 = install_v14_runtime_bridges()
        scan_wrapper = _install_scan_wrapper()
        _INSTALLED = bool(v14.get("installed") and scan_wrapper.get("installed"))
        return {
            **status(),
            "v14": v14,
            "scan_wrapper": scan_wrapper,
        }


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED
        wrapper = _SCAN_WRAPPER_INSTALLED
    from workstation.risk_geometry_v141 import status as geometry_status

    geometry = geometry_status()
    return {
        "success": True,
        "version": "14.1",
        "service": "JARVIS_RISK_GEOMETRY_CONVERGENCE_V14_1",
        "installed": installed,
        "scan_wrapper_installed": wrapper,
        "geometry": geometry,
        "upstream_legacy_qualification_can_suppress_geometry": False if installed else None,
        "invalid_risk_levels_hard_blocker_preserved": True,
        "v14_positive_ev_authority_preserved": True,
        "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
    }


__all__ = ["install_v141_runtime_bridges", "status"]
