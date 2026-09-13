"""V16 HTTP convergence layer for the professional paper terminal.

The professional terminal remains the runtime authority. This module exposes
its canonical ``workspace_state`` snapshot on the V16 route while leaving the
existing ``/api/terminal/*`` endpoints available as compatibility shims. It
never places broker orders and never creates a second trading engine.
"""
from __future__ import annotations

import json
import secrets
import urllib.parse

from workstation.professional_terminal import build_handler as build_compat_handler


CANONICAL_WORKSPACE_STATE_PATH = "/api/v16/trading/workspace-state"
RECONCILIATION_PATH = "/api/v16/trading/reconciliation"
OPTION_ORDER_PATH = "/api/v16/trading/option-order"
REPAIR_RECONCILIATION_PATH = "/api/v16/trading/reconcile"


def _safety(payload):
    result = dict(payload or {})
    result["paper_only"] = True
    result["live_execution"] = False
    result["automatic_broker_order"] = False
    result["live_orders_locked"] = True
    result["naked_option_selling"] = False
    return result


def build_handler(base, runtime):
    """Wrap the existing local handler with canonical V16 routes."""

    CompatHandler = build_compat_handler(base, runtime)

    class V16TerminalHandler(CompatHandler):
        def send_json(self, payload, status=200):
            """A browser tab disappearing is not a trading-runtime failure."""
            try:
                return super().send_json(payload, status)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return None

        def _authorized_v16_write(self):
            return bool(
                self._local()
                and secrets.compare_digest(
                    str(self.headers.get("X-Jarvis-Token", "")),
                    str(runtime.token),
                )
            )

        def _v16_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768:
                raise ValueError("Invalid request size")
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("JSON object required")
            return value

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/" and self._local():
                from workstation.quant_terminal_v2 import STATIC

                content = (
                    (STATIC / "index.html")
                    .read_text(encoding="utf-8")
                    .replace(
                        "</head>",
                        "<script>window.JARVIS_V16_CANONICAL=true;</script></head>",
                    )
                    .encode("utf-8")
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return

            if parsed.path == RECONCILIATION_PATH:
                if not self._local():
                    return self.send_json({"success": False, "message": "Local terminal only"}, 403)
                return self.send_json(_safety(runtime.reconcile()))

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
            return self.send_json(_safety(payload))

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path not in {OPTION_ORDER_PATH, REPAIR_RECONCILIATION_PATH}:
                return super().do_POST()
            if not self._authorized_v16_write():
                return self.send_json(
                    _safety(
                        {
                            "success": False,
                            "reason": "LOCAL_SESSION_TOKEN_REQUIRED",
                            "message": "Refresh this local terminal before changing paper state.",
                        }
                    ),
                    403,
                )
            try:
                body = self._v16_body()
                if parsed.path == OPTION_ORDER_PATH:
                    from workstation.v16_option_paper import option_order

                    return self.send_json(_safety(option_order(runtime, body)))

                from workstation.v16_option_paper import repair_legacy_links

                repaired = repair_legacy_links(runtime.desk)
                reconciliation = runtime.reconcile(integrity=True)
                return self.send_json(
                    _safety(
                        {
                            "success": bool(reconciliation.get("success")),
                            "repair": repaired,
                            "reconciliation": reconciliation,
                            "message": (
                                "Canonical ledger links are reconciled."
                                if reconciliation.get("success")
                                else "Unresolved ledger issues remain; no new exposure is permitted."
                            ),
                        }
                    )
                )
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                return self.send_json(
                    _safety({"success": False, "message": str(exc)}),
                    400,
                )

    return V16TerminalHandler


__all__ = [
    "CANONICAL_WORKSPACE_STATE_PATH",
    "RECONCILIATION_PATH",
    "OPTION_ORDER_PATH",
    "REPAIR_RECONCILIATION_PATH",
    "build_handler",
]
