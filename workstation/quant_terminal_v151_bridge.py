from __future__ import annotations

import urllib.parse
from threading import RLock
from typing import Any

from workstation import quant_terminal_v2 as quant
from workstation.quant_terminal_v15_bridge import QuantTerminalV15Handler


_LOCK = RLock()
_INSTALLED = False


class QuantTerminalV151Handler(QuantTerminalV15Handler):
    _jarvis_v151_options = True
    server_version = "JARVISQuant-V15.1OptionsBridge/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v151_options_execution_runtime.js":
            return self.send_file(quant.STATIC / "v151_options_execution_runtime.js", "application/javascript; charset=utf-8")
        if path == "/api/v15.1/options/status":
            from workstation.options_runtime_v151 import status
            return self.send_json(status())
        if path == "/api/v15.1/options/plan":
            symbol = str((params.get("symbol") or ["NIFTY"])[0]).strip().upper() or "NIFTY"
            provider = str((params.get("provider") or ["fyers"])[0]).strip().lower() or "fyers"
            from workstation.options_runtime_v151 import plan
            return self.send_json(plan(symbol, provider_name=provider))
        if path == "/api/v15.1/status":
            from workstation.v151_runtime_bridges import status as runtime_status
            from workstation.options_runtime_v151 import status as options_status
            runtime = runtime_status()
            options = options_status()
            return self.send_json({
                "success": True,
                "version": "15.1",
                "service": "JARVIS_QUANT_V151_OPTIONS_EXECUTION_INTELLIGENCE",
                "runtime": runtime,
                "options": options,
                "v15_market_reasoning_preserved": runtime.get("v15_market_reasoning_preserved") is True,
                "v141_risk_geometry_preserved": runtime.get("v141_risk_geometry_preserved") is True,
                "read_only_chain_provider_preserved": True,
                "long_premium_only": True,
                "naked_option_selling": False,
                "verified_option_chain_required": True,
                "verified_instrument_spec_required": True,
                "dealer_positioning": "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY",
                "permanent_agents": 29,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        return super().do_GET()


def install_quant_terminal_v151_bridge() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        if getattr(quant.Handler, "_jarvis_v151_options", False):
            _INSTALLED = True
            return status()
        quant.Handler = QuantTerminalV151Handler
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED or getattr(quant.Handler, "_jarvis_v151_options", False)
    return {
        "success": True,
        "version": "15.1",
        "service": "JARVIS_QUANT_V151_HTTP_BRIDGE",
        "installed": bool(installed),
        "v15_endpoints_preserved": True,
        "options_asset": (quant.STATIC / "v151_options_execution_runtime.js").is_file(),
        "read_only_http_surface": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = ["QuantTerminalV151Handler", "install_quant_terminal_v151_bridge", "status"]
