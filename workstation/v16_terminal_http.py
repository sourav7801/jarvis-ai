"""V16 HTTP convergence layer for the professional paper terminal.

The V15/V16 professional terminal remains the runtime authority. This module
only exposes its canonical ``workspace_state`` snapshot on the V16 route while
leaving the existing ``/api/terminal/*`` endpoints available as compatibility
shims. It never places broker orders and never creates a second trading engine.
"""
from __future__ import annotations

import urllib.parse

from workstation.professional_terminal import build_handler as build_compat_handler


CANONICAL_WORKSPACE_STATE_PATH = "/api/v16/trading/workspace-state"


def build_handler(base, runtime):
    """Wrap the existing local handler with the canonical V16 state route."""

    CompatHandler = build_compat_handler(base, runtime)

    class V16TerminalHandler(CompatHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != CANONICAL_WORKSPACE_STATE_PATH:
                return super().do_GET()

            if not self._local():
                return self.send_json(
                    {"success": False, "message": "Local terminal only"},
                    403,
                )

            params = urllib.parse.parse_qs(parsed.query)
            name = str(params.get("workspace", ["INTRADAY"])[0]).upper()
            try:
                payload = runtime.workspace_state(name)
            except (ValueError, KeyError) as exc:
                return self.send_json({"success": False, "message": str(exc)}, 400)

            # Safety contract is asserted again at the HTTP boundary so future
            # refactors cannot accidentally expose an execution-capable state.
            payload = dict(payload)
            payload["paper_only"] = True
            payload["live_execution"] = False
            payload["automatic_broker_order"] = False
            payload["live_orders_locked"] = True
            return self.send_json(payload)

    return V16TerminalHandler


__all__ = ["CANONICAL_WORKSPACE_STATE_PATH", "build_handler"]
