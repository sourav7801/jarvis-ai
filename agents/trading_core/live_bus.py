
from __future__ import annotations

import importlib
from typing import Any, Dict, Optional


class LiveBus:
    """Reads configured JARVIS market-data streams without owning them."""

    def stream_status(self) -> Dict[str, Any]:
        fyers_status = None
        try:
            mod = importlib.import_module("agents.fyers_live_stream")
            stream = getattr(mod, "fyers_live_stream")
            fyers_status = stream.status()
            if fyers_status.get("running"):
                return fyers_status
        except Exception:
            pass
        try:
            mod = importlib.import_module("agents.upstox_live_stream")
            stream = getattr(mod, "upstox_live_stream")
            status = {
                "provider": "UPSTOX",
                "running": bool(stream.store.is_running()),
            }
            if status["running"]:
                return status
            return fyers_status or status
        except Exception as exc:
            return fyers_status or {
                "provider": "UPSTOX",
                "running": False,
                "error": str(exc),
            }

    def snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            mod = importlib.import_module("agents.fyers_live_stream")
            stream = getattr(mod, "fyers_live_stream")
            result = stream.snapshot(symbol)
            if result:
                return result
        except Exception:
            pass
        try:
            mod = importlib.import_module("agents.upstox_live_stream")
            stream = getattr(mod, "upstox_live_stream")
            return stream.snapshot(symbol)
        except Exception:
            return None
