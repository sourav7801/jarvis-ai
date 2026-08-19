from __future__ import annotations

import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from agents.fyers_live_stream import fyers_live_stream
from workstation.paper_market_data import UnifiedPaperMarketData

HOST = os.getenv("JARVIS_FYERS_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_FYERS_BRIDGE_PORT", "8790"))

_INDEX_SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")
_COMMODITY_SYMBOLS = ("CRUDEOIL", "GOLD", "SILVER", "NATURALGAS")
_ALIAS_MAP: dict[str, str] = {}
_START_ERROR = ""
_LOCK = threading.RLock()


def _commodity_provider_symbol(symbol: str) -> str:
    service = UnifiedPaperMarketData(
        fyers_quote_loader=lambda *_a, **_k: (_ for _ in ()).throw(
            RuntimeError("quote loader disabled during symbol resolution")
        ),
        fyers_history_loader=lambda *_a, **_k: (_ for _ in ()).throw(
            RuntimeError("history loader disabled during symbol resolution")
        ),
    )
    resolved = service.provider_symbol(symbol)
    provider_symbol = str(resolved.get("provider_symbol") or "").strip().upper()
    if not provider_symbol:
        raise RuntimeError(f"Could not resolve active FYERS contract for {symbol}.")
    return provider_symbol


def _resolved_symbols() -> list[str]:
    global _ALIAS_MAP
    aliases: dict[str, str] = {}
    provider_symbols: list[str] = []

    from agents.fyers_data_adapter import normalize_symbol

    for symbol in _INDEX_SYMBOLS:
        provider = normalize_symbol(symbol)
        aliases[symbol] = provider
        provider_symbols.append(provider)

    for symbol in _COMMODITY_SYMBOLS:
        try:
            provider = _commodity_provider_symbol(symbol)
        except Exception:
            continue
        aliases[symbol] = provider
        provider_symbols.append(provider)

    _ALIAS_MAP = aliases
    return list(dict.fromkeys(provider_symbols))


def start_stream() -> dict[str, Any]:
    global _START_ERROR
    try:
        fyers_live_stream.stop()
    except Exception:
        pass

    try:
        symbols = _resolved_symbols()
        if not symbols:
            raise RuntimeError("No FYERS symbols could be resolved for the live bridge.")
        result = fyers_live_stream.start(symbols, lite_mode=False)
        _START_ERROR = ""
        return result
    except Exception as exc:
        _START_ERROR = f"{type(exc).__name__}: {exc}"[:500]
        return status_payload()


def status_payload() -> dict[str, Any]:
    try:
        status = dict(fyers_live_stream.status())
    except Exception as exc:
        status = {
            "provider": "FYERS",
            "running": False,
            "connected": False,
            "symbols": [],
            "snapshots": 0,
            "error": f"{type(exc).__name__}: {exc}",
            "data_only": True,
        }

    with _LOCK:
        return {
            **status,
            "error": status.get("error") or _START_ERROR or None,
            "aliases": dict(_ALIAS_MAP),
            "data_only": True,
            "live_orders": False,
            "service": "isolated_fyers_live_bridge",
        }


def snapshot_payload(symbol: str) -> dict[str, Any]:
    alias = str(symbol or "").strip().upper().replace(" ", "")
    if alias == "NATURALGAS":
        canonical = "NATURALGAS"
    elif alias == "CRUDEOIL":
        canonical = "CRUDEOIL"
    else:
        canonical = alias

    provider = _ALIAS_MAP.get(canonical, canonical)
    snapshot = fyers_live_stream.snapshot(provider)
    if not snapshot:
        return {
            "success": False,
            "symbol": canonical,
            "provider_symbol": provider,
            "snapshot": None,
            "status": status_payload(),
            "message": "No FYERS live snapshot is available yet.",
            "live_orders": False,
        }

    safe = {key: value for key, value in dict(snapshot).items() if key != "raw"}
    return {
        "success": True,
        "symbol": canonical,
        "provider_symbol": provider,
        "snapshot": safe,
        "status": status_payload(),
        "live_orders": False,
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            return self.send_json(status_payload())
        if parsed.path == "/api/snapshot":
            params = urllib.parse.parse_qs(parsed.query)
            symbol = str((params.get("symbol") or [""])[0]).strip()
            payload = snapshot_payload(symbol)
            return self.send_json(payload, 200 if payload.get("success") else 503)
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "data_only": True, "live_orders": False})
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/restart":
            return self.send_json(start_stream())
        self.send_error(404)

    def log_message(self, *_args) -> None:
        pass


def main() -> int:
    print("=" * 64)
    print("JARVIS FYERS LIVE DATA BRIDGE")
    print("=" * 64)
    print(f"http://{HOST}:{PORT}")
    print("Read-only SymbolUpdate market data")
    print("Live broker orders: LOCKED")
    start_stream()
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        fyers_live_stream.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
