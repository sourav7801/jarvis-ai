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
LEGACY_POSITION_PATH = "/api/v16/trading/legacy-position"
LEGACY_RESOLUTION_PATH = LEGACY_POSITION_PATH + "/resolve"


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

        def _authorized_legacy_write(self):
            """Require the local session token plus a loopback request boundary.

            The legacy resolver mutates the retired JSON book as part of an
            audited reconciliation. Keep that write surface narrower than the
            ordinary paper-session endpoints: the TCP peer must be loopback and
            browser requests must originate from an HTTP loopback origin. A
            token-authenticated non-browser loopback caller may omit Origin.
            """
            if not self._authorized_v16_write():
                return False
            if self.client_address[0] not in {"127.0.0.1", "::1"}:
                return False
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urllib.parse.urlparse(origin)
            return bool(
                parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost"}
                and not parsed.username
                and not parsed.password
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
                        "<script>window.JARVIS_V16_CANONICAL=true;</script>"
                        "<link rel=\"stylesheet\" href=\"/v16_autonomy_runtime.css\">"
                        "<script defer src=\"/v16_autonomy_runtime.js\"></script></head>",
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

            if parsed.path == "/v16_option_execution.js" and self._local():
                from workstation.quant_terminal_v2 import STATIC

                return self.send_file(
                    STATIC / "v16_option_execution.js",
                    "application/javascript; charset=utf-8",
                )

            if parsed.path in {"/v16_autonomy_runtime.js", "/v16_autonomy_runtime.css"} and self._local():
                from workstation.quant_terminal_v2 import STATIC

                return self.send_file(
                    STATIC / parsed.path[1:],
                    "application/javascript; charset=utf-8"
                    if parsed.path.endswith(".js")
                    else "text/css; charset=utf-8",
                )

            if parsed.path == RECONCILIATION_PATH:
                if not self._local():
                    return self.send_json({"success": False, "message": "Local terminal only"}, 403)
                return self.send_json(_safety(runtime.reconcile()))

            if parsed.path == LEGACY_POSITION_PATH:
                if not self._local():
                    return self.send_json({"success": False, "message": "Local terminal only"}, 403)
                from workstation.v16_legacy_resolution import legacy_resolution_details

                return self.send_json(_safety(legacy_resolution_details(runtime)))

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
            if parsed.path not in {
                OPTION_ORDER_PATH,
                REPAIR_RECONCILIATION_PATH,
                LEGACY_RESOLUTION_PATH,
            }:
                return super().do_POST()
            authorized = (
                self._authorized_legacy_write()
                if parsed.path == LEGACY_RESOLUTION_PATH
                else self._authorized_v16_write()
            )
            if not authorized:
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
                if parsed.path == LEGACY_RESOLUTION_PATH:
                    from workstation.v16_legacy_resolution import resolve_legacy_position

                    resolved = resolve_legacy_position(runtime, body)
                    resolved["reconciliation"] = runtime.reconcile(integrity=True)
                    return self.send_json(_safety(resolved))
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
    "LEGACY_POSITION_PATH",
    "LEGACY_RESOLUTION_PATH",
    "build_handler",
]
