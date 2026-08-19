from __future__ import annotations

"""Public, read-only BTC/ETH option intelligence from Deribit.

No account credentials or trading methods are used.  The adapter combines the
public instrument catalogue with public option book summaries and feeds the
existing generic JARVIS option-chain intelligence layer.
"""

from datetime import datetime, timezone
import json
import time
import urllib.parse
import urllib.request
from typing import Any

from omni.trading_intelligence.derivatives_confirmation import derivatives_confirmation
from omni.trading_intelligence.option_chain_intelligence import option_chain_intelligence
from omni.trading_intelligence.option_chain_schema import OptionChainSnapshot, OptionContractQuote


BASE_URL = "https://www.deribit.com/api/v2"
SUPPORTED_CURRENCIES = {"BTC", "ETH"}
_CACHE: dict[tuple[str, str], tuple[float, Any]] = {}


def _json(method: str, params: dict[str, Any], timeout: float = 8.0) -> Any:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{BASE_URL}/{method}?{query}",
        headers={"Accept": "application/json", "User-Agent": "JARVIS-Quant-V3-ReadOnly/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=float(timeout)) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise RuntimeError("Deribit returned a non-object response.")
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload.get("result")


def _cached(method: str, currency: str, *, ttl: float, timeout: float = 8.0) -> Any:
    key = (method, currency)
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] <= max(0.0, float(ttl)):
        return cached[1]
    if method == "instruments":
        result = _json(
            "public/get_instruments",
            {"currency": currency, "kind": "option", "expired": "false"},
            timeout=timeout,
        )
    else:
        result = _json(
            "public/get_book_summary_by_currency",
            {"currency": currency, "kind": "option"},
            timeout=timeout,
        )
    _CACHE[key] = (now, result)
    return result


def _expiry_iso(milliseconds: Any) -> str:
    try:
        stamp = float(milliseconds) / 1000.0
        return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()
    except Exception:
        return "unknown"


def fetch_deribit_option_chain(
    currency: str,
    *,
    expiry_timestamp: int | None = None,
    strike_window: int = 16,
    timeout: float = 8.0,
) -> dict[str, Any]:
    currency = str(currency or "").strip().upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError("Deribit Quant V3 currently supports public BTC and ETH options.")

    started = time.perf_counter_ns()
    instruments = _cached("instruments", currency, ttl=30.0, timeout=timeout) or []
    summaries = _cached("summaries", currency, ttl=2.0, timeout=timeout) or []
    instrument_map = {
        str(item.get("instrument_name")): item
        for item in instruments
        if isinstance(item, dict) and item.get("instrument_name")
    }
    summary_map = {
        str(item.get("instrument_name")): item
        for item in summaries
        if isinstance(item, dict) and item.get("instrument_name")
    }

    expiries = sorted(
        {
            int(item.get("expiration_timestamp"))
            for item in instrument_map.values()
            if item.get("expiration_timestamp") is not None
        }
    )
    if not expiries:
        raise RuntimeError("Deribit returned no active option expiries.")
    selected_expiry = int(expiry_timestamp) if expiry_timestamp else expiries[0]
    if selected_expiry not in expiries:
        selected_expiry = min(expiries, key=lambda value: abs(value - selected_expiry))

    candidates = []
    underlying_prices = []
    for name, meta in instrument_map.items():
        if int(meta.get("expiration_timestamp") or 0) != selected_expiry:
            continue
        summary = summary_map.get(name, {})
        strike = meta.get("strike")
        option_type = str(meta.get("option_type") or "").lower()
        if strike is None or option_type not in {"call", "put"}:
            continue
        underlying = summary.get("underlying_price")
        if underlying is not None:
            try:
                underlying_prices.append(float(underlying))
            except Exception:
                pass
        mark = summary.get("mark_price")
        bid = summary.get("bid_price")
        ask = summary.get("ask_price")
        # Deribit option prices are quoted in the base currency.  Keep the
        # provider-native premium in metadata; option-chain structure/OI/IV is
        # still valid for research and paper selection.
        premium = mark if mark is not None else bid if bid is not None else ask
        if premium is None:
            continue
        candidates.append(
            {
                "name": name,
                "strike": float(strike),
                "option_type": option_type,
                "premium": max(0.0, float(premium)),
                "bid": float(bid) if bid is not None else None,
                "ask": float(ask) if ask is not None else None,
                "volume": summary.get("volume"),
                "open_interest": summary.get("open_interest"),
                "iv": summary.get("mark_iv"),
                "underlying_price": underlying,
            }
        )

    if not candidates:
        raise RuntimeError("Deribit returned no usable option book summaries for the selected expiry.")
    spot = float(underlying_prices[-1]) if underlying_prices else 0.0
    if spot <= 0:
        raise RuntimeError("Deribit option summaries did not contain a valid underlying price.")

    strikes = sorted({row["strike"] for row in candidates})
    atm = min(strikes, key=lambda strike: abs(strike - spot))
    window = max(2, min(int(strike_window), 50))
    atm_index = strikes.index(atm)
    allowed = set(strikes[max(0, atm_index - window) : atm_index + window + 1])
    selected = [row for row in candidates if row["strike"] in allowed]

    contracts = tuple(
        OptionContractQuote(
            underlying=currency,
            expiry=_expiry_iso(selected_expiry),
            strike=row["strike"],
            option_type=row["option_type"],
            ltp=row["premium"],
            symbol=row["name"],
            bid=row["bid"],
            ask=row["ask"],
            volume=row["volume"],
            open_interest=row["open_interest"],
            change_in_oi=None,
            implied_volatility=row["iv"],
        )
        for row in selected
    )
    snapshot = OptionChainSnapshot(
        underlying=currency,
        spot=spot,
        timestamp=datetime.now(timezone.utc).isoformat(),
        contracts=contracts,
    )
    analysis = option_chain_intelligence.analyze(snapshot)
    confirmation = derivatives_confirmation(analysis)
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
    return {
        "success": True,
        "provider": "DERIBIT_PUBLIC",
        "currency": currency,
        "spot": spot,
        "selected_expiry": selected_expiry,
        "expiry": _expiry_iso(selected_expiry),
        "available_expiries": expiries,
        "contract_count": len(contracts),
        "analysis": analysis,
        "confirmation": confirmation,
        "contracts": [contract.to_dict() for contract in contracts],
        "latency_ms": round(elapsed_ms, 3),
        "credentials_required": False,
        "defined_risk_required": True,
        "naked_short_options_allowed": False,
        "paper_only": True,
        "live_execution": False,
        "broker_order": False,
    }


def __getattr__(name: str):
    lower = str(name).lower()
    if any(token in lower for token in ("place", "modify", "cancel", "execute", "order", "buy", "sell")):
        raise PermissionError("Deribit Quant V3 adapter exposes public market data only.")
    raise AttributeError(name)
