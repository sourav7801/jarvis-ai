from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
_LAST_STATUS: dict[str, Any] = {}


def install_v12_runtime_bridges() -> dict[str, Any]:
    """Install process-local V12 paper/intelligence compatibility bridges.

    Protected HTTP routes and legacy module names remain available, but the
    canonical paper-autonomy singleton and direct trade command authority are
    rebound to V12 adaptive expected-value intelligence inside the current
    process. This is deliberately process-local and never changes live broker
    execution, which remains unavailable/locked.
    """

    global _INSTALLED, _LAST_STATUS
    with _LOCK:
        from workstation.adaptive_direct_trade_bridge import install_adaptive_direct_trade_bridge
        from workstation.adaptive_paper_autonomy_engine import adaptive_paper_autonomy
        from workstation import paper_autonomy_engine as legacy_autonomy_module

        direct = install_adaptive_direct_trade_bridge()
        legacy_autonomy_module.paper_autonomy = adaptive_paper_autonomy

        # If Quant has already been imported, prevent its legacy boot helper
        # from becoming a second execution owner. The canonical V12 portfolio
        # controller is started explicitly by start_jarvis_quant_terminal.py.
        quant_auto_start = None
        try:
            from workstation import quant_terminal_v2

            quant_terminal_v2.AUTO_PAPER_START = False
            quant_auto_start = False
        except Exception:
            pass

        _INSTALLED = True
        _LAST_STATUS = {
            "success": True,
            "version": "12.0",
            "installed": True,
            "adaptive_direct_trade": dict(direct),
            "legacy_paper_autonomy_alias": (
                legacy_autonomy_module.paper_autonomy is adaptive_paper_autonomy
            ),
            "legacy_quant_auto_start": quant_auto_start,
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
        return dict(_LAST_STATUS)


def status() -> dict[str, Any]:
    with _LOCK:
        if _LAST_STATUS:
            return dict(_LAST_STATUS)
        return {
            "success": True,
            "version": "12.0",
            "installed": _INSTALLED,
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = ["install_v12_runtime_bridges", "status"]
