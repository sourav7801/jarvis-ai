from __future__ import annotations

"""Non-invasive HTTP extension for the V2 professional terminal."""

import json
import urllib.parse
from typing import Any

from workstation.quant_v3_extension import quant_v3_extension


_INSTALLED = False


def install(trading_app) -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    quant_v3_extension.configure(
        candle_loader=trading_app.candles_payload,
        live_loader=trading_app.live_payload,
    )

    handler = trading_app.Handler
    original_get = handler.do_GET
    original_post = handler.do_POST

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = parsed.path

        if path == "/quant_v3.js":
            return self.send_file(
                trading_app.STATIC / "quant_v3.js",
                "application/javascript; charset=utf-8",
            )
        if path == "/api/v3/status":
            return self.send_json(quant_v3_extension.status_payload())
        if path == "/api/v3/strategies":
            return self.send_json(quant_v3_extension.strategies_payload())
        if path == "/api/v3/autopilot/status":
            return self.send_json(quant_v3_extension.autopilot.status())
        if path == "/api/v3/decision":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                payload = quant_v3_extension.decision_payload(symbol)
                return self.send_json(payload, 200 if payload.get("success") else 503)
            except Exception as exc:
                return self.send_json(
                    {
                        "success": False,
                        "message": f"{type(exc).__name__}: {exc}"[:500],
                        "paper_only": True,
                        "live_execution": False,
                    },
                    400,
                )
        if path == "/api/v3/options":
            try:
                symbol = str((params.get("symbol") or ["NIFTY"])[0])
                payload = quant_v3_extension.option_payload(symbol)
                status = 200 if isinstance(payload, dict) and payload.get("success") else 503
                return self.send_json(payload or {"success": False}, status)
            except Exception as exc:
                return self.send_json(
                    {
                        "success": False,
                        "message": f"{type(exc).__name__}: {exc}"[:500],
                        "paper_only": True,
                        "live_execution": False,
                    },
                    400,
                )
        return original_get(self)

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/v3/"):
            return original_post(self)

        body = _body(self)
        try:
            if path == "/api/v3/autopilot/start":
                symbols = body.get("symbols")
                if isinstance(symbols, str):
                    symbols = [item.strip() for item in symbols.split(",") if item.strip()]
                if not isinstance(symbols, (list, tuple)):
                    symbols = None
                return self.send_json(quant_v3_extension.start_autopilot(symbols))
            if path == "/api/v3/autopilot/stop":
                return self.send_json(quant_v3_extension.autopilot.stop())
            if path == "/api/v3/autopilot/kill":
                reason = str(body.get("reason") or "manual_ui_kill")
                return self.send_json(quant_v3_extension.autopilot.kill(reason))
            if path == "/api/v3/autopilot/resume":
                return self.send_json(quant_v3_extension.autopilot.resume())
            if path == "/api/v3/decision":
                symbol = str(body.get("symbol") or "NIFTY")
                payload = quant_v3_extension.decision_payload(symbol)
                return self.send_json(payload, 200 if payload.get("success") else 503)
        except Exception as exc:
            return self.send_json(
                {
                    "success": False,
                    "message": f"{type(exc).__name__}: {exc}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                },
                400,
            )
        self.send_error(404)

    handler.do_GET = do_GET
    handler.do_POST = do_POST
    handler._quant_v3_installed = True
    _INSTALLED = True
