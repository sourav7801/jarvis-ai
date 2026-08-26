from __future__ import annotations

from typing import Any


def options_readiness_payload() -> dict[str, Any]:
    try:
        from agents.fyers_auth_manager import FyersSettings, is_configured

        settings = FyersSettings.from_env()
        fyers_configured = bool(is_configured())
        token_saved = bool(settings.token_file.exists())
    except Exception:
        fyers_configured = False
        token_saved = False

    return {
        "success": True,
        "india_index_options": {
            "provider": "FYERS_READ_ONLY",
            "underlyings": ["NIFTY", "BANKNIFTY"],
            "configured": fyers_configured,
            "token_saved": token_saved,
            "capabilities": [
                "expiry discovery",
                "option chain",
                "bid/ask and spread",
                "open interest and change in OI",
                "volume",
                "implied volatility",
                "delta gamma theta vega",
                "put-call OI ratio",
                "exact-contract historical chart",
                "defined-risk paper intent",
            ],
            "limitations": [
                "stock-option chain scanning is not yet enabled",
                "dynamic Indian option WebSocket subscription is not enabled",
                "naked short-option paper intents are blocked",
                "broker orders are absent",
            ],
        },
        "crypto_options": {
            "provider": "DERIBIT_PUBLIC",
            "underlyings": ["BTC", "ETH"],
            "credentials_required": False,
            "capabilities": [
                "public option instrument discovery",
                "ticker and volatility fields",
                "historical option candles",
                "paper-only contract analysis",
            ],
            "limitations": ["no exchange order adapter", "public data is research-only"],
        },
        "live_execution": {
            "state": "LOCKED",
            "reason": (
                "No audited order adapter, exchange credential vault, pre-trade risk service, "
                "kill switch, reconciliation loop, or explicit live authorization is installed."
            ),
        },
        "paper_only": True,
    }

