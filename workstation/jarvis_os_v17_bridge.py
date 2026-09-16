"""V17 unified workstation bridge over the verified V16 Master surface.

The UI/workspace/capability implementation remains the verified V16 bridge.
V17 changes the product identity and reports the autonomous-options runtime
without introducing a second Master or browser execution authority.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v16_bridge as v16

HOST = v16.HOST
PORT = v16.PORT


def _v17_status() -> dict[str, Any]:
    payload = dict(v16._v16_status())
    trading = dict(payload.get("trading") or {})
    trading.update(
        {
            "autonomy": "JARVIS_V17_AUTONOMOUS_OPTIONS",
            "manual_option_selection_required": False,
            "verified_auto_option_underlyings": ["BANKNIFTY", "NIFTY", "SENSEX"],
            "broad_market_scanning": True,
            "forced_trade_quota": False,
            "paper_only": True,
            "live_orders_locked": True,
        }
    )
    payload.update(
        {
            "version": "17.0",
            "service": "JARVIS_MASTER_V17_AUTONOMOUS_OPTIONS",
            "verified_parent": "V16_TRADING_CONVERGENCE",
            "trading": trading,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
    )
    return payload


class V17BridgeHandler(v16.V16BridgeHandler):
    server_version = "JarvisOSV8-V17Bridge/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/v17/status":
            return self.send_json(_v17_status())
        return super().do_GET()


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V17BridgeHandler)


__all__ = ["HOST", "PORT", "V17BridgeHandler", "create_server", "_v17_status"]
