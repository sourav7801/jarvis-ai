"""V14 Quant HTTP overlay for continuous paper execution intelligence."""
from __future__ import annotations

import urllib.parse
from threading import RLock
from typing import Any

from workstation import quant_terminal_v2 as quant
from workstation.quant_terminal_v13_bridge import QuantTerminalV13Handler


_LOCK = RLock()
_INSTALLED = False


class QuantTerminalV14Handler(QuantTerminalV13Handler):
    """Preserve V13 assets/endpoints and add V14 execution observability."""

    _jarvis_v14_execution = True
    server_version = "JARVISQuant-V14Bridge/1.0"

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/v14_execution_runtime.js":
            return self.send_file(
                quant.STATIC / "v14_execution_runtime.js",
                "application/javascript; charset=utf-8",
            )
        if path == "/api/v14/execution-authority":
            from omni.trading_intelligence.continuous_execution_policy_v14 import (
                CONTINUOUS_EXECUTION_POLICY_V14,
            )
            from workstation.v14_runtime_bridges import status as runtime_status
            from workstation.paper_execution_sizing_v13 import status as sizing_status

            return self.send_json({
                "success": True,
                "version": "14.0",
                "service": "JARVIS_QUANT_V14_EXECUTION_AUTHORITY",
                "policy": CONTINUOUS_EXECUTION_POLICY_V14.status(),
                "runtime": runtime_status(),
                "sizing": sizing_status(),
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        if path == "/api/v14/opportunity-lifecycle":
            from workstation.opportunity_lifecycle_v14 import OPPORTUNITY_LIFECYCLE_V14

            return self.send_json(OPPORTUNITY_LIFECYCLE_V14.snapshot(limit=160))
        return super().do_GET()


def install_quant_terminal_v14_bridge() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        if getattr(quant.Handler, "_jarvis_v14_execution", False):
            _INSTALLED = True
            return status()
        quant.Handler = QuantTerminalV14Handler
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED or getattr(quant.Handler, "_jarvis_v14_execution", False)
    asset = quant.STATIC / "v14_execution_runtime.js"
    return {
        "success": True,
        "version": "14.0",
        "service": "JARVIS_QUANT_V14_HTTP_BRIDGE",
        "installed": bool(installed),
        "v13_assets_preserved": True,
        "v14_execution_asset": asset.is_file(),
        "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = ["QuantTerminalV14Handler", "install_quant_terminal_v14_bridge", "status"]
