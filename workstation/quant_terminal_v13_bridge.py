"""V13 process-local Quant HTTP overlay.

The protected Quant handler remains the implementation for market data, paper
execution and legacy assets. V13 only adds the generation-specific read-only
runtime assets/identity endpoint that the V13 HTML references. No broker-order
surface is added.
"""
from __future__ import annotations

import urllib.parse
from threading import RLock
from typing import Any

from workstation import quant_terminal_v2 as quant


_LOCK = RLock()
_INSTALLED = False
_BASE_HANDLER = quant.Handler


class QuantTerminalV13Handler(_BASE_HANDLER):
    """Serve V12/V13 UI overlays while delegating all core Quant behavior."""

    _jarvis_v13_assets = True
    server_version = "JARVISQuant-V13Bridge/1.0"

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/v12_paper_intelligence.js":
            return self.send_file(
                quant.STATIC / "v12_paper_intelligence.js",
                "application/javascript; charset=utf-8",
            )
        if path == "/v13_contextual_paper_runtime.js":
            return self.send_file(
                quant.STATIC / "v13_contextual_paper_runtime.js",
                "application/javascript; charset=utf-8",
            )
        if path == "/api/v13/runtime-assets":
            v12_asset = quant.STATIC / "v12_paper_intelligence.js"
            v13_asset = quant.STATIC / "v13_contextual_paper_runtime.js"
            return self.send_json(
                {
                    "success": v12_asset.is_file() and v13_asset.is_file(),
                    "version": "13.0",
                    "service": "JARVIS_QUANT_V13_RUNTIME_ASSETS",
                    "handler_installed": True,
                    "assets": {
                        "v12_paper_intelligence": v12_asset.is_file(),
                        "v13_contextual_paper_runtime": v13_asset.is_file(),
                    },
                    "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
                    "paper_only": True,
                    "live_execution": False,
                    "automatic_broker_order": False,
                }
            )
        return super().do_GET()


def install_quant_terminal_v13_bridge() -> dict[str, Any]:
    """Install the overlay exactly once in the current Quant process."""

    global _INSTALLED
    with _LOCK:
        if getattr(quant.Handler, "_jarvis_v13_assets", False):
            _INSTALLED = True
            return status()
        quant.Handler = QuantTerminalV13Handler
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED or getattr(quant.Handler, "_jarvis_v13_assets", False)
    return {
        "success": True,
        "version": "13.0",
        "installed": bool(installed),
        "service": "JARVIS_QUANT_V13_HTTP_BRIDGE",
        "v12_paper_intelligence_asset": (quant.STATIC / "v12_paper_intelligence.js").is_file(),
        "v13_contextual_paper_asset": (quant.STATIC / "v13_contextual_paper_runtime.js").is_file(),
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = [
    "QuantTerminalV13Handler",
    "install_quant_terminal_v13_bridge",
    "status",
]
