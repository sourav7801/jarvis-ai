
from __future__ import annotations

import importlib
import os
from typing import Any, Dict, Optional


class DataBus:
    def __init__(self) -> None:
        preferred = os.getenv("JARVIS_MARKET_DATA_PROVIDER", "AUTO").strip().upper()
        self.providers = []
        if preferred in {"", "AUTO", "FYERS"}:
            self.providers.append(
                ("agents.fyers_data_adapter", "get_intraday_data")
            )
        # Keep the existing Zerodha/Upstox adapter as a safe fallback.  Setting
        # FYERS as preferred changes only data priority, never order execution.
        self.providers.append(
            ("agents.broker_intraday_adapter", "get_intraday_data")
        )

    def get_history(self, symbol: str, timeframe: str, bars: int = 1000) -> Dict[str, Any]:
        errors = []
        for module_name, func_name in self.providers:
            try:
                module = importlib.import_module(module_name)
                fn = getattr(module, func_name)
                result = fn(symbol=symbol, market="india", timeframe=timeframe, bars=bars)
                if isinstance(result, dict) and result.get("success"):
                    return result
                errors.append(str(result.get("message")) if isinstance(result, dict) else "invalid result")
            except Exception as exc:
                errors.append(str(exc))

        if timeframe == "5m":
            try:
                loader = importlib.import_module("agents.upstox_historical_loader")
                fn = getattr(loader, "get_symbol_5m", None)
                if callable(fn):
                    result = fn(symbol=symbol, bars=bars)
                    if isinstance(result, dict) and result.get("success"):
                        return result
            except Exception as exc:
                errors.append(str(exc))

        return {
            "success": False,
            "source": "UNAVAILABLE",
            "data_quality": "UNAVAILABLE",
            "message": " | ".join(errors[-5:]) or "No provider available.",
            "data": None,
            "bars": 0,
        }

    def live_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
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

    def live_status(self) -> dict[str, Any]:
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
            status = {"provider": "UPSTOX", "running": bool(stream.store.is_running())}
            if status["running"]:
                return status
            return fyers_status or status
        except Exception as exc:
            return fyers_status or {
                "provider": "UPSTOX",
                "running": False,
                "error": str(exc),
            }
