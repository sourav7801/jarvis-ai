
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import requests


TOKEN_FILE = Path.home() / "Documents" / "JARVIS_Trading" / "upstox_token.json"

UNDERLYINGS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
}


class OptionConfirmation:
    """
    Reads the Upstox option-chain endpoint and turns OI/volume/greeks into
    deterministic confirmation metrics.

    It does not place orders.
    """

    def __init__(self, timeout=10):
        self.timeout = timeout

    def token(self) -> str:
        try:
            data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            return str(data.get("access_token", "")).strip()
        except Exception:
            return ""

    def fetch_chain(self, symbol: str, expiry: str = "current_week"):
        key = UNDERLYINGS.get(symbol.upper())
        if not key:
            return {"success": False, "reason": f"Unsupported option underlying: {symbol}"}
        token = self.token()
        if not token:
            return {"success": False, "reason": "No Upstox access token."}

        url = "https://api.upstox.com/v2/option/chain"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        params = {
            "instrument_key": key,
            "expiry_date": expiry,
        }

        try:
            r = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            if r.status_code != 200:
                return {
                    "success": False,
                    "http": r.status_code,
                    "reason": r.text[:800],
                }
            payload = r.json()
            return {
                "success": payload.get("status") == "success",
                "data": payload.get("data", []),
                "underlying": key,
                "expiry": expiry,
            }
        except Exception as exc:
            return {"success": False, "reason": str(exc)}

    @staticmethod
    def summarize(symbol: str, chain_result: dict[str, Any]) -> dict[str, Any]:
        if not chain_result.get("success"):
            return {
                "available": False,
                "confirmed": False,
                "reason": chain_result.get("reason", "Option chain unavailable."),
            }

        rows = chain_result.get("data") or []
        if not rows:
            return {
                "available": False,
                "confirmed": False,
                "reason": "Option chain returned no rows.",
            }

        pcr_values = []
        call_oi = put_oi = 0.0
        call_vol = put_vol = 0.0

        for row in rows:
            pcr = row.get("pcr")
            if pcr is not None:
                try:
                    pcr_values.append(float(pcr))
                except Exception:
                    pass

            call = row.get("call_options") or {}
            put = row.get("put_options") or {}

            cm = call.get("market_data") or {}
            pm = put.get("market_data") or {}

            call_oi += float(cm.get("oi", 0) or 0)
            put_oi += float(pm.get("oi", 0) or 0)
            call_vol += float(cm.get("volume", 0) or 0)
            put_vol += float(pm.get("volume", 0) or 0)

        pcr_avg = sum(pcr_values) / len(pcr_values) if pcr_values else (
            put_oi / max(call_oi, 1.0)
        )

        oi_pressure = "PUT_HEAVY" if put_oi > call_oi * 1.1 else (
            "CALL_HEAVY" if call_oi > put_oi * 1.1 else "BALANCED"
        )
        volume_pressure = "PUT_HEAVY" if put_vol > call_vol * 1.1 else (
            "CALL_HEAVY" if call_vol > put_vol * 1.1 else "BALANCED"
        )

        return {
            "available": True,
            "confirmed": True,
            "symbol": symbol,
            "rows": len(rows),
            "pcr_avg": round(pcr_avg, 3),
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "oi_pressure": oi_pressure,
            "volume_pressure": volume_pressure,
            "reason": "Option-chain data available.",
        }

    def confirm(self, symbol: str, expiry: str = "current_week"):
        raw = self.fetch_chain(symbol, expiry)
        summary = self.summarize(symbol, raw)
        summary["expiry_request"] = expiry
        return summary
