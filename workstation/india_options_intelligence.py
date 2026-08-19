from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import json
import math
import urllib.parse
import urllib.request
from typing import Any

from agents.fyers_auth_manager import FyersSettings, load_token


FYERS_DATA_BASE = "https://api-t1.fyers.in/data"
FYERS_NSE_FO_MASTER = "https://public.fyers.in/sym_details/NSE_FO_sym_master.json"

UNDERLYINGS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
}


@dataclass(frozen=True)
class IndiaOptionRequest:
    underlying: str
    strike: float | None
    option_type: str | None
    expiry_date: str | None
    expiry_mode: str
    paper_requested: bool
    buy_requested: bool
    sell_requested: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _authorization_header() -> str:
    settings = FyersSettings.from_env()
    payload = load_token(settings)
    if payload is None:
        raise RuntimeError("FYERS login is required before reading the option chain.")
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("FYERS token file does not contain an access token.")
    prefix = f"{settings.app_id}:"
    return token if token.startswith(prefix) else prefix + token


def _fyers_json(path: str, params: dict[str, Any], timeout: float = 6.0) -> dict[str, Any]:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    request = urllib.request.Request(
        f"{FYERS_DATA_BASE}{path}?{query}",
        headers={
            "Authorization": _authorization_header(),
            "User-Agent": "JARVIS-Quant-Research/3.2",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("FYERS option-chain response was not a JSON object.")
    if str(payload.get("s") or "").lower() not in {"ok", "success"}:
        raise RuntimeError(str(payload.get("message") or "FYERS option-chain request failed."))
    return payload


def _resolve_underlying(text: str) -> str | None:
    compact = " ".join(str(text or "").lower().replace("-", " ").split())
    if "bank nifty" in compact or "banknifty" in compact or "nifty bank" in compact:
        return "BANKNIFTY"
    if "nifty 50" in compact or "nifty50" in compact or "nifty" in compact:
        return "NIFTY"
    return None


def parse_india_option_request(text: str, *, today: date | None = None) -> IndiaOptionRequest | None:
    import re

    raw = " ".join(str(text or "").strip().lower().replace("-", " ").split())
    if not raw or not any(token in raw for token in ("option", "call", "put", "ce", "pe", "expiry")):
        return None
    underlying = _resolve_underlying(raw)
    if underlying is None:
        return None

    option_type = None
    if re.search(r"\b(call|ce)\b", raw):
        option_type = "CE"
    elif re.search(r"\b(put|pe)\b", raw):
        option_type = "PE"

    numbers = [float(value) for value in re.findall(r"(?<![a-z])\b(\d{4,6}(?:\.\d+)?)\b", raw)]
    strike = numbers[0] if numbers else None

    base = today or datetime.now().date()
    expiry_date = None
    expiry_mode = "NEAREST"
    if "tomorrow" in raw:
        expiry_date = (base + timedelta(days=1)).isoformat()
        expiry_mode = "EXACT_DATE"
    elif "monthly" in raw or "month expiry" in raw:
        expiry_mode = "MONTHLY"
    elif "weekly" in raw or "week expiry" in raw or "next expiry" in raw:
        expiry_mode = "NEAREST"

    return IndiaOptionRequest(
        underlying=underlying,
        strike=strike,
        option_type=option_type,
        expiry_date=expiry_date,
        expiry_mode=expiry_mode,
        paper_requested="paper" in raw,
        buy_requested=bool(re.search(r"\b(buy|long)\b", raw)),
        sell_requested=bool(re.search(r"\b(sell|short)\b", raw)),
    )


def _expiry_iso(row: dict[str, Any]) -> str | None:
    value = str(row.get("date") or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


def _choose_expiry(expiries: list[dict[str, Any]], request: IndiaOptionRequest) -> dict[str, Any] | None:
    rows = [row for row in expiries if isinstance(row, dict) and row.get("expiry")]
    if not rows:
        return None
    if request.expiry_date:
        exact = [row for row in rows if _expiry_iso(row) == request.expiry_date]
        return exact[0] if exact else None
    if request.expiry_mode == "MONTHLY":
        monthly = [row for row in rows if str(row.get("expiry_flag") or "").upper() == "M"]
        return monthly[0] if monthly else rows[0]
    return rows[0]


def fetch_option_chain(
    underlying: str,
    *,
    strikecount: int = 10,
    expiry_epoch: str | None = None,
    greeks: bool = True,
) -> dict[str, Any]:
    canonical = str(underlying or "").upper()
    provider_symbol = UNDERLYINGS.get(canonical)
    if not provider_symbol:
        raise ValueError(f"Unsupported India option-chain underlying: {underlying}")
    return _fyers_json(
        "/options-chain-v3",
        {
            "symbol": provider_symbol,
            "strikecount": max(1, min(int(strikecount), 50)),
            "timestamp": expiry_epoch,
            "greeks": "1" if greeks else None,
        },
    )


def _chain_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("optionsChain") if isinstance(data, dict) else None
    return [dict(row) for row in rows or [] if isinstance(row, dict)]


def _spot(rows: list[dict[str, Any]]) -> float | None:
    for row in rows:
        if str(row.get("option_type") or "") == "":
            value = _safe_float(row.get("ltp"))
            if value is not None:
                return value
    return None


def _selected_contract(rows: list[dict[str, Any]], request: IndiaOptionRequest) -> dict[str, Any] | None:
    candidates = [row for row in rows if str(row.get("option_type") or "").upper() in {"CE", "PE"}]
    if request.option_type:
        candidates = [row for row in candidates if str(row.get("option_type") or "").upper() == request.option_type]
    if not candidates:
        return None
    if request.strike is None:
        spot = _spot(rows)
        if spot is None:
            return None
        return min(candidates, key=lambda row: abs(float(row.get("strike_price") or 0.0) - spot))
    exact = [row for row in candidates if _safe_float(row.get("strike_price")) == float(request.strike)]
    if exact:
        return exact[0]
    return min(candidates, key=lambda row: abs(float(row.get("strike_price") or 0.0) - float(request.strike)))


def _normalize_contract(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    greeks = row.get("greeks") if isinstance(row.get("greeks"), dict) else {}
    bid = _safe_float(row.get("bid"))
    ask = _safe_float(row.get("ask"))
    mid = ((bid + ask) / 2.0) if bid is not None and ask is not None and ask >= bid else None
    return {
        "symbol": row.get("symbol"),
        "strike": _safe_float(row.get("strike_price")),
        "option_type": str(row.get("option_type") or "").upper(),
        "ltp": _safe_float(row.get("ltp")),
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread": (ask - bid) if ask is not None and bid is not None else None,
        "open_interest": _safe_int(row.get("oi")),
        "change_in_oi": _safe_int(row.get("oich")),
        "volume": _safe_int(row.get("volume")),
        "iv": _safe_float(greeks.get("iv")),
        "delta": _safe_float(greeks.get("delta")),
        "gamma": _safe_float(greeks.get("gamma")),
        "theta": _safe_float(greeks.get("theta")),
        "vega": _safe_float(greeks.get("vega")),
    }


def analyze_india_option_request(text: str, *, today: date | None = None) -> dict[str, Any] | None:
    request = parse_india_option_request(text, today=today)
    if request is None:
        return None

    first = fetch_option_chain(request.underlying, strikecount=2, greeks=False)
    data = first.get("data") if isinstance(first, dict) else {}
    expiries = list(data.get("expiryData") or []) if isinstance(data, dict) else []
    chosen = _choose_expiry(expiries, request)
    if request.expiry_date and chosen is None:
        available_dates = [value for value in (_expiry_iso(row) for row in expiries) if value]
        return {
            "action": "india_option_analysis",
            "success": False,
            "request": request.to_dict(),
            "available_expiries": available_dates,
            "speech": (
                f"No listed {request.underlying} option expiry matches {request.expiry_date}. "
                + (f"Nearest listed expiry is {available_dates[0]}." if available_dates else "No expiry data was returned.")
            ),
            "paper_intent": None,
            "risk_gate": "EXPIRY_UNAVAILABLE",
            "paper_only": True,
            "live_execution": False,
        }

    expiry_epoch = str(chosen.get("expiry")) if chosen else None
    full = fetch_option_chain(request.underlying, strikecount=12, expiry_epoch=expiry_epoch, greeks=True)
    rows = _chain_rows(full)
    contract = _normalize_contract(_selected_contract(rows, request))
    spot = _spot(rows)
    full_data = full.get("data") if isinstance(full, dict) else {}
    call_oi = _safe_float(full_data.get("callOi")) if isinstance(full_data, dict) else None
    put_oi = _safe_float(full_data.get("putOi")) if isinstance(full_data, dict) else None
    pcr = (put_oi / call_oi) if put_oi is not None and call_oi not in (None, 0) else None

    if request.option_type is None:
        speech = (
            f"{request.underlying} option request recognized. "
            f"Expiry {(_expiry_iso(chosen) if chosen else 'nearest')} and strike {request.strike or 'ATM'} were resolved, "
            "but CALL or PUT is missing. No paper position was opened."
        )
        paper_intent = None
        risk_gate = "OPTION_TYPE_REQUIRED"
    elif contract is None:
        speech = "No verified matching option contract was returned by FYERS. No paper position was opened."
        paper_intent = None
        risk_gate = "CONTRACT_UNAVAILABLE"
    elif request.sell_requested and request.paper_requested:
        speech = "Naked short-option paper execution is blocked by the current JARVIS risk policy. Analyze a defined-risk spread instead."
        paper_intent = None
        risk_gate = "NAKED_SHORT_OPTION_BLOCKED"
    elif request.paper_requested and request.buy_requested:
        ref = contract.get("ask") or contract.get("mid") or contract.get("ltp")
        paper_intent = {
            "status": "PAPER_OPTION_INTENT",
            "underlying": request.underlying,
            "symbol": contract.get("symbol"),
            "option_type": request.option_type,
            "strike": contract.get("strike"),
            "expiry": _expiry_iso(chosen) if chosen else None,
            "side": "BUY",
            "quantity_lots": 1,
            "entry_reference": ref,
            "provider": "FYERS_READ_ONLY",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "live_execution": False,
        }
        speech = (
            f"Paper option intent created for {request.underlying} {contract.get('strike'):g} {request.option_type} "
            f"expiring {paper_intent['expiry']}. Live execution remains locked."
        )
        risk_gate = "PAPER_OPTION_INTENT_CREATED"
    else:
        paper_intent = None
        risk_gate = "ANALYSIS_ONLY"
        speech = (
            f"Verified {request.underlying} option: {contract.get('strike'):g} {request.option_type}, "
            f"expiry {(_expiry_iso(chosen) if chosen else 'nearest')}, LTP {contract.get('ltp')}, IV {contract.get('iv')}. "
            "Research only; no trade was placed."
        )

    return {
        "action": "india_option_analysis",
        "success": contract is not None or request.option_type is None,
        "request": request.to_dict(),
        "provider": "FYERS_READ_ONLY",
        "provider_symbol": UNDERLYINGS[request.underlying],
        "expiry": dict(chosen) if chosen else None,
        "spot": spot,
        "contract": contract,
        "pcr_oi": pcr,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "paper_intent": paper_intent,
        "risk_gate": risk_gate,
        "speech": speech,
        "paper_only": True,
        "live_execution": False,
    }
