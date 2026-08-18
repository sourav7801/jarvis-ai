
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

TOKEN_FILE = Path.home() / "Documents" / "JARVIS_Trading" / "upstox_token.json"

UNDERLYINGS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
}

# User policy:
# - BANKNIFTY preferred only around expiry / prior trading day when momentum is strong.
# - NIFTY/SENSEX otherwise.
EXPIRY_PREFERENCE = {
    "NIFTY": ["current_week", "next_week"],
    "BANKNIFTY": ["current_month", "next_month"],
    "SENSEX": ["current_week", "next_week", "current_month"],
}


class OptionConfirmationV2:
    def __init__(self, timeout: int = 12):
        self.timeout = timeout

    def token(self) -> str:
        try:
            payload = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            return str(payload.get("access_token", "")).strip()
        except Exception:
            return ""

    def _headers(self) -> dict[str, str]:
        token = self.token()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def get_contracts(self, symbol: str, expiry: str | None = None) -> dict[str, Any]:
        key = UNDERLYINGS.get(symbol.upper())
        token = self.token()
        if not key:
            return {"success": False, "reason": f"Unsupported symbol: {symbol}"}
        if not token:
            return {"success": False, "reason": "No access token."}

        params = {"instrument_key": key}
        if expiry:
            params["expiry_date"] = expiry

        try:
            r = requests.get(
                "https://api.upstox.com/v2/option/contract",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            payload = r.json()
            return {
                "success": r.status_code == 200 and payload.get("status") == "success",
                "http": r.status_code,
                "data": payload.get("data", []),
                "reason": payload.get("message") or payload.get("errors"),
                "used_params": params,
            }
        except Exception as exc:
            return {
                "success": False,
                "reason": str(exc),
                "used_params": params,
            }

    def discover_expiry(self, symbol: str) -> dict[str, Any]:
        """
        Try relative expiry keywords first. If the contract endpoint returns
        concrete contracts, take the nearest valid expiry date from them.
        """
        symbol = symbol.upper()
        attempts = EXPIRY_PREFERENCE.get(symbol, ["current_week", "next_week"])

        diagnostics = []

        for keyword in attempts:
            result = self.get_contracts(symbol, keyword)
            diagnostics.append(
                {
                    "keyword": keyword,
                    "success": result.get("success"),
                    "http": result.get("http"),
                    "rows": len(result.get("data") or []),
                }
            )

            rows = result.get("data") or []
            if rows:
                expiries = sorted(
                    {
                        str(x.get("expiry"))
                        for x in rows
                        if x.get("expiry")
                    }
                )
                if expiries:
                    return {
                        "success": True,
                        "symbol": symbol,
                        "keyword": keyword,
                        "expiry": expiries[0],
                        "contracts": rows,
                        "diagnostics": diagnostics,
                    }

        # Last attempt: request unfiltered contract list and derive nearest
        # future expiry from the returned contracts.
        result = self.get_contracts(symbol, None)
        rows = result.get("data") or []
        future = []
        now = datetime.now(timezone.utc).date()

        for row in rows:
            raw = row.get("expiry")
            if not raw:
                continue
            try:
                d = datetime.strptime(
                    str(raw), "%Y-%m-%d"
                ).date()
            except Exception:
                continue
            if d >= now:
                future.append(d)

        if future:
            d = min(future)
            return {
                "success": True,
                "symbol": symbol,
                "keyword": "discovered",
                "expiry": d.isoformat(),
                "contracts": rows,
                "diagnostics": diagnostics + [
                    {
                        "keyword": "unfiltered",
                        "success": result.get("success"),
                        "http": result.get("http"),
                        "rows": len(rows),
                    }
                ],
            }

        return {
            "success": False,
            "symbol": symbol,
            "reason": "No usable future option expiry/contracts were returned by Upstox.",
            "diagnostics": diagnostics,
        }

    def get_chain(self, symbol: str, expiry: str) -> dict[str, Any]:
        key = UNDERLYINGS.get(symbol.upper())
        if not key:
            return {
                "success": False,
                "reason": f"Unsupported symbol: {symbol}",
            }

        try:
            r = requests.get(
                "https://api.upstox.com/v2/option/chain",
                params={
                    "instrument_key": key,
                    "expiry_date": expiry,
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            payload = r.json()
            return {
                "success": r.status_code == 200 and payload.get("status") == "success",
                "http": r.status_code,
                "data": payload.get("data", []),
                "reason": payload.get("message") or payload.get("errors"),
                "expiry": expiry,
            }
        except Exception as exc:
            return {
                "success": False,
                "reason": str(exc),
                "expiry": expiry,
            }

    @staticmethod
    def summarize(symbol: str, chain: dict[str, Any]) -> dict[str, Any]:
        rows = chain.get("data") or []
        if not chain.get("success"):
            return {
                "available": False,
                "confirmed": False,
                "reason": chain.get("reason") or "Option chain request failed.",
                "http": chain.get("http"),
                "expiry": chain.get("expiry"),
            }

        if not rows:
            return {
                "available": False,
                "confirmed": False,
                "reason": "Option chain returned zero strikes.",
                "expiry": chain.get("expiry"),
            }

        put_oi = call_oi = put_vol = call_vol = 0.0
        pcr_values = []

        for row in rows:
            pcr = row.get("pcr")
            if pcr is not None:
                try:
                    pcr_values.append(float(pcr))
                except Exception:
                    pass

            c = row.get("call_options") or {}
            p = row.get("put_options") or {}
            cm = c.get("market_data") or {}
            pm = p.get("market_data") or {}

            call_oi += float(cm.get("oi", 0) or 0)
            put_oi += float(pm.get("oi", 0) or 0)
            call_vol += float(cm.get("volume", 0) or 0)
            put_vol += float(pm.get("volume", 0) or 0)

        pcr = (
            sum(pcr_values) / len(pcr_values)
            if pcr_values
            else put_oi / max(call_oi, 1.0)
        )

        return {
            "available": True,
            "confirmed": True,
            "symbol": symbol,
            "expiry": chain.get("expiry"),
            "strikes": len(rows),
            "spot": rows[0].get("underlying_spot_price"),
            "pcr": round(pcr, 3),
            "call_oi": call_oi,
            "put_oi": put_oi,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "oi_pressure": (
                "PUT_HEAVY" if put_oi > call_oi * 1.10
                else "CALL_HEAVY" if call_oi > put_oi * 1.10
                else "BALANCED"
            ),
            "volume_pressure": (
                "PUT_HEAVY" if put_vol > call_vol * 1.10
                else "CALL_HEAVY" if call_vol > put_vol * 1.10
                else "BALANCED"
            ),
            "reason": "Live option-chain data available.",
        }

    def confirm(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        discovery = self.discover_expiry(symbol)
        if not discovery.get("success"):
            return {
                "available": False,
                "confirmed": False,
                "stage": "EXPIRY_DISCOVERY",
                "reason": discovery.get("reason"),
                "diagnostics": discovery.get("diagnostics", []),
            }

        expiry = discovery["expiry"]
        chain = self.get_chain(symbol, expiry)
        result = self.summarize(symbol, chain)
        result["expiry_source"] = discovery.get("keyword")
        result["expiry_diagnostics"] = discovery.get("diagnostics", [])
        return result
