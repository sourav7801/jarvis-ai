from __future__ import annotations

"""Read-only FYERS option-chain provider for Quant V3.

This module intentionally implements only the market-data endpoint.  It reads
an already-saved FYERS access token from the existing local auth manager and
never exposes order placement, modification, cancellation, or broker writes.
"""

from datetime import datetime, timezone
import json
import time
import urllib.parse
import urllib.request
from typing import Any

from agents.fyers_auth_manager import FyersSettings, load_token
from omni.trading_intelligence.derivatives_confirmation import derivatives_confirmation
from omni.trading_intelligence.fyers_chain_normalizer import normalize_fyers_option_chain
from omni.trading_intelligence.option_chain_intelligence import option_chain_intelligence
from omni.trading_intelligence.option_chain_schema import OptionChainSnapshot, OptionContractQuote


DATA_HOST = "https://api-t1.fyers.in/data"
DEFAULT_STRIKE_COUNT = 12
MAX_STRIKE_COUNT = 50

FRIENDLY_UNDERLYINGS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}

_CACHE: dict[tuple[str, int, str | None, bool], tuple[float, dict[str, Any]]] = {}


def provider_symbol(value: str) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if ":" in text:
        return str(value).strip().upper()
    return FRIENDLY_UNDERLYINGS.get(text, text)


def _authorization_header(settings: FyersSettings, token: str) -> str:
    token = str(token or "").strip()
    prefix = f"{settings.app_id}:"
    return token if token.startswith(prefix) else prefix + token


def _request_json(path: str, params: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    settings = FyersSettings.from_env()
    settings.validate(require_secret=False)
    payload = load_token(settings)
    if not payload:
        raise RuntimeError("FYERS login is required before option-chain research can run.")
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Saved FYERS token does not contain an access token.")

    query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
    request = urllib.request.Request(
        DATA_HOST + path + "?" + query,
        headers={
            "Authorization": _authorization_header(settings, access_token),
            "Accept": "application/json",
            "User-Agent": "JARVIS-Quant-V3-ReadOnly/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=float(timeout)) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise RuntimeError("FYERS option-chain response was not a JSON object.")
    return data


def fetch_fyers_option_chain(
    underlying: str,
    *,
    strikecount: int = DEFAULT_STRIKE_COUNT,
    expiry_timestamp: int | str | None = None,
    greeks: bool = True,
    cache_seconds: float = 2.0,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch and normalize the FYERS v3 option chain without broker writes."""

    symbol = provider_symbol(underlying)
    strikes = max(1, min(int(strikecount), MAX_STRIKE_COUNT))
    expiry_key = str(expiry_timestamp) if expiry_timestamp not in (None, "") else None
    key = (symbol, strikes, expiry_key, bool(greeks))
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] <= max(0.0, float(cache_seconds)):
        return {**cached[1], "cache_hit": True}

    request_payload: dict[str, Any] = {
        "symbol": symbol,
        "strikecount": strikes,
        "greeks": 1 if greeks else 0,
    }
    if expiry_timestamp not in (None, ""):
        request_payload["timestamp"] = expiry_timestamp

    started = time.perf_counter_ns()
    response = _request_json("/options-chain-v3", request_payload, timeout=timeout)
    normalized = normalize_fyers_option_chain(
        {
            "response": response,
            "request": request_payload,
            "sdk_version": "rest-data-v3",
        }
    )
    normalized = {
        **normalized,
        "latency_ms": round((time.perf_counter_ns() - started) / 1_000_000.0, 3),
        "cache_hit": False,
        "paper_only": True,
        "live_execution": False,
        "broker_order": False,
    }
    _CACHE[key] = (now, normalized)
    return normalized


def _snapshot(normalized: dict[str, Any]) -> OptionChainSnapshot:
    spot = float(normalized.get("spot") or 0.0)
    if spot <= 0:
        raise ValueError("FYERS option-chain response did not contain a valid underlying spot.")
    expiry = str(normalized.get("selected_expiry") or "unknown")
    contracts = []
    for leg in normalized.get("legs") or ():
        option_type = str(leg.get("option_type") or "").upper()
        if option_type not in {"CE", "PE"}:
            continue
        ltp = leg.get("ltp")
        strike = leg.get("strike")
        if ltp is None or strike is None:
            continue
        contracts.append(
            OptionContractQuote(
                underlying=str(normalized.get("symbol") or ""),
                expiry=str(leg.get("expiry") or expiry),
                strike=float(strike),
                option_type=option_type,
                ltp=max(0.0, float(ltp)),
                symbol=leg.get("symbol"),
                bid=leg.get("bid"),
                ask=leg.get("ask"),
                volume=leg.get("volume"),
                open_interest=leg.get("oi"),
                change_in_oi=leg.get("oi_change"),
                implied_volatility=leg.get("iv"),
                delta=leg.get("delta"),
                gamma=leg.get("gamma"),
                theta=leg.get("theta"),
                vega=leg.get("vega"),
            )
        )
    if not contracts:
        raise ValueError("FYERS option-chain response contained no usable option contracts.")
    return OptionChainSnapshot(
        underlying=str(normalized.get("symbol") or ""),
        spot=spot,
        timestamp=str(normalized.get("captured_at") or datetime.now(timezone.utc).isoformat()),
        contracts=tuple(contracts),
    )


def analyze_fyers_options(
    underlying: str,
    *,
    strikecount: int = DEFAULT_STRIKE_COUNT,
    expiry_timestamp: int | str | None = None,
    greeks: bool = True,
    underlying_return: float | None = None,
    futures_return: float | None = None,
    futures_basis_pct: float | None = None,
) -> dict[str, Any]:
    normalized = fetch_fyers_option_chain(
        underlying,
        strikecount=strikecount,
        expiry_timestamp=expiry_timestamp,
        greeks=greeks,
    )
    snapshot = _snapshot(normalized)
    analysis = option_chain_intelligence.analyze(snapshot)
    confirmation = derivatives_confirmation(
        analysis,
        underlying_return=underlying_return,
        futures_return=futures_return,
        futures_basis_pct=futures_basis_pct,
    )
    return {
        "success": True,
        "provider": "FYERS",
        "symbol": normalized.get("symbol"),
        "spot": normalized.get("spot"),
        "expiry": normalized.get("selected_expiry"),
        "expiry_data": normalized.get("expiry_data"),
        "analysis": analysis,
        "confirmation": confirmation,
        "legs": list(normalized.get("legs") or ()),
        "latency_ms": normalized.get("latency_ms"),
        "cache_hit": normalized.get("cache_hit", False),
        "defined_risk_required": True,
        "naked_short_options_allowed": False,
        "paper_only": True,
        "live_execution": False,
        "broker_order": False,
    }


def __getattr__(name: str):
    lower = str(name).lower()
    if any(token in lower for token in ("place", "modify", "cancel", "execute", "order", "buy", "sell")):
        raise PermissionError("Quant V3 FYERS option-chain provider is read-only.")
    raise AttributeError(name)
