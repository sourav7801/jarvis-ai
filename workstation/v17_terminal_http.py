"""V17 HTTP layer for the professional autonomous-options PAPER terminal.

This wraps the canonical V16 terminal handler without creating another trading
engine.  It adds a V17 runtime-status endpoint and serves a V17-branded shell
only when the V17 launcher is used.
"""
from __future__ import annotations

import urllib.parse

from workstation.v16_terminal_http import build_handler as build_v16_handler

V17_STATUS_PATH = "/api/v17/trading/status"


def _v17_status(runtime, workspace: str) -> dict:
    service = getattr(runtime, "v17_autonomy_service", None)
    if service is None:
        return {
            "success": False,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.0",
            "installed": False,
            "reason": "V17_AUTONOMY_SERVICE_NOT_INSTALLED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "live_orders_locked": True,
        }
    payload = dict(service.status(workspace))
    payload.update(
        {
            "success": True,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.0",
            "runtime_identity": "V17_AUTONOMOUS_OPTIONS",
            "verified_parent": "V16_TRADING_CONVERGENCE",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "live_orders_locked": True,
        }
    )
    return payload


def build_handler(base, runtime):
    V16Handler = build_v16_handler(base, runtime)

    class V17TerminalHandler(V16Handler):
        server_version = "JarvisQuantV17/1.0"

        def _serve_v17_root(self):
            from workstation.quant_terminal_v2 import STATIC

            html = (STATIC / "index.html").read_text(encoding="utf-8")
            html = html.replace('<script src="/paper_desk_runtime.js"></script>', "")
            html = html.replace(
                "V15 AUTONOMOUS MARKET REASONING · PAPER / RESEARCH",
                "V17 AUTONOMOUS OPTIONS RUNTIME · PAPER / RESEARCH",
            )
            html = html.replace(
                "JARVIS Quant V15 ·",
                "JARVIS Quant V17 · autonomous options ·",
            )
            html = html.replace(
                "JARVIS V15 reasons across verified market state",
                "JARVIS V17 uses the verified V15 reasoning core across market state",
            )
            injection = (
                '<script>window.JARVIS_V16_CANONICAL=true;window.JARVIS_V17_RUNTIME=true;</script>'
                '<link rel="stylesheet" href="/v16_autonomy_runtime.css">'
                '<script defer src="/v16_autonomy_runtime.js"></script>'
                '<script defer src="/v16_option_decision_runtime.js"></script>'
                '<script defer src="/v16_workspace_router.js"></script>'
                '<script defer src="/v16_option_experience_runtime.js"></script>'
                '<script defer src="/v16_option_readiness_runtime.js"></script>'
                '<script defer src="/v17_runtime.js"></script>'
            )
            content = html.replace("</head>", injection + "</head>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == "/" and self._local():
                return self._serve_v17_root()

            if parsed.path == "/v17_runtime.js" and self._local():
                from workstation.quant_terminal_v2 import STATIC

                return self.send_file(
                    STATIC / "v17_runtime.js",
                    "application/javascript; charset=utf-8",
                )

            if parsed.path == V17_STATUS_PATH:
                if not self._local():
                    return self.send_json(
                        {
                            "success": False,
                            "reason": "LOCAL_TERMINAL_ONLY",
                            "paper_only": True,
                            "live_execution": False,
                        },
                        403,
                    )
                params = urllib.parse.parse_qs(parsed.query)
                workspace = str(params.get("workspace", ["INTRADAY"])[0]).upper()
                return self.send_json(_v17_status(runtime, workspace))

            return super().do_GET()

    return V17TerminalHandler


__all__ = ["V17_STATUS_PATH", "build_handler"]
