"""V17 HTTP layer for the professional autonomous-options PAPER terminal.

This wraps the canonical V16 terminal handler without creating another trading
engine. It adds one route-aware V17 status surface and exposes read-only FYERS
stream health without starting a second market-data engine.
"""
from __future__ import annotations

import urllib.parse

from workstation.v16_terminal_http import build_handler as build_v16_handler

V17_STATUS_PATH = "/api/v17/trading/status"

_ROUTE_META = {
    "INTRADAY": {
        "label": "Intraday",
        "execution_workspace": "INTRADAY",
        "horizon": "SESSION",
    },
    "SWING": {
        "label": "Swing",
        "execution_workspace": "SWING",
        "horizon": "MULTI_SESSION",
    },
    "INVESTMENT": {
        "label": "Investment",
        "execution_workspace": "INVESTMENT",
        "horizon": "POSITIONAL",
    },
    # OPTIONS is a dedicated workstation route, but the current verified
    # autonomous option bridge executes through the canonical INTRADAY paper
    # workspace. Preserve both identities instead of silently rewriting it.
    "OPTIONS": {
        "label": "Options",
        "execution_workspace": "INTRADAY",
        "horizon": "INTRADAY_DERIVATIVES",
    },
}


def _route_metadata(workspace: str) -> dict:
    raw = str(workspace or "INTRADAY").strip().upper()
    requested = raw if raw in _ROUTE_META else "INTRADAY"
    meta = dict(_ROUTE_META[requested])
    return {
        "id": requested,
        "requested_workspace": requested,
        "execution_workspace": meta["execution_workspace"],
        "label": meta["label"],
        "horizon": meta["horizon"],
        "fallback_applied": raw not in _ROUTE_META,
        "requested_raw": raw,
    }


def _fyers_stream_status() -> dict:
    """Return a secret-free observation of the singleton FYERS data stream."""
    try:
        from agents.fyers_live_stream import fyers_live_stream

        payload = dict(fyers_live_stream.status())
    except Exception as exc:
        payload = {
            "provider": "FYERS",
            "transport": "DATA_WEBSOCKET",
            "state": "UNAVAILABLE",
            "running": False,
            "connected": False,
            "fresh": False,
            "error": f"{type(exc).__name__}: {exc}",
            "data_only": True,
            "read_only": True,
            "order_socket_enabled": False,
            "live_order_execution": False,
        }

    # Enforce the HTTP contract even if an older singleton implementation is
    # imported during a rolling local update.
    payload["data_only"] = True
    payload["read_only"] = True
    payload["order_socket_enabled"] = False
    payload["live_order_execution"] = False
    return payload


def _v17_status(runtime, workspace: str) -> dict:
    route = _route_metadata(workspace)
    safety = {
        "mode": "PAPER_RESEARCH_ONLY",
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "live_orders_locked": True,
    }
    market_data = {
        "primary_provider": "FYERS",
        "read_only": True,
        "stream": _fyers_stream_status(),
    }

    service = getattr(runtime, "v17_autonomy_service", None)
    if service is None:
        return {
            "success": False,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.0",
            "installed": False,
            "reason": "V17_AUTONOMY_SERVICE_NOT_INSTALLED",
            "workspace": route["requested_workspace"],
            "execution_workspace": route["execution_workspace"],
            "route": route,
            "market_data": market_data,
            "safety": safety,
            **safety,
        }

    payload = dict(service.status(route["execution_workspace"]))
    payload.update(
        {
            "success": True,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.0",
            "runtime_identity": "V17_AUTONOMOUS_OPTIONS",
            "verified_parent": "V16_TRADING_CONVERGENCE",
            "workspace": route["requested_workspace"],
            "execution_workspace": route["execution_workspace"],
            "route": route,
            "market_data": market_data,
            "safety": safety,
            **safety,
        }
    )
    return payload


def build_handler(base, runtime):
    V16Handler = build_v16_handler(base, runtime)

    class V17TerminalHandler(V16Handler):
        server_version = "JarvisQuantV17/1.1"

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


__all__ = [
    "V17_STATUS_PATH",
    "_fyers_stream_status",
    "_route_metadata",
    "_v17_status",
    "build_handler",
]
