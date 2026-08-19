from __future__ import annotations

from copy import deepcopy
import json
import os
import urllib.request
from typing import Any


MASTER_URLS = {
    "NSE": "https://public.fyers.in/sym_details/NSE_FO_sym_master.json",
    "BSE": "https://public.fyers.in/sym_details/BSE_FO_sym_master.json",
    "MCX": "https://public.fyers.in/sym_details/MCX_COM_sym_master.json",
}


def _read_master(exchange: str, timeout: float = 8.0) -> dict[str, Any]:
    url = MASTER_URLS.get(str(exchange or "").upper())
    if not url:
        raise ValueError(f"Unsupported exchange for option validation: {exchange}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "JARVIS-Quant-Research/3.2"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("FYERS symbol master returned an invalid payload.")
    return payload


def contract_record(symbol: str) -> dict[str, Any] | None:
    value = str(symbol or "").strip()
    if ":" not in value:
        return None
    exchange = value.split(":", 1)[0].upper()
    master = _read_master(exchange)
    row = master.get(value)
    return dict(row) if isinstance(row, dict) else None


def lot_size(symbol: str) -> int | None:
    row = contract_record(symbol)
    if not row:
        return None
    for key in ("minLotSize", "lotSize", "lot_size"):
        try:
            value = int(float(row.get(key)))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def validate_india_option_paper_payload(
    payload: dict[str, Any] | None,
    *,
    equity: float | None = None,
    max_premium_fraction: float | None = None,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    result = deepcopy(payload)
    intent = result.get("paper_intent")
    if not isinstance(intent, dict):
        return result

    symbol = str(intent.get("symbol") or "")
    try:
        resolved_lot = lot_size(symbol)
    except Exception as exc:
        resolved_lot = None
        validation_error = str(exc)[:240]
    else:
        validation_error = None

    if not resolved_lot:
        result["paper_intent"] = None
        result["risk_gate"] = "LOT_SIZE_UNVERIFIED"
        result["speech"] = (
            "The option contract was found, but JARVIS could not verify its current FYERS lot size. "
            "No paper position was opened."
        )
        if validation_error:
            result["validation_error"] = validation_error
        return result

    paper_equity = float(
        equity if equity is not None else os.getenv("JARVIS_PAPER_EQUITY", "100000")
    )
    premium_fraction = float(
        max_premium_fraction
        if max_premium_fraction is not None
        else os.getenv("JARVIS_OPTION_MAX_PREMIUM_FRACTION", "0.20")
    )
    entry = intent.get("entry_reference")
    try:
        entry_value = float(entry)
    except (TypeError, ValueError):
        entry_value = 0.0

    estimated_premium = entry_value * resolved_lot
    max_premium = max(0.0, paper_equity * premium_fraction)
    if entry_value <= 0 or estimated_premium <= 0:
        result["paper_intent"] = None
        result["risk_gate"] = "OPTION_PRICE_UNAVAILABLE"
        result["speech"] = "A verified option premium was unavailable. No paper position was opened."
        return result

    if estimated_premium > max_premium:
        result["paper_intent"] = None
        result["risk_gate"] = "PREMIUM_BUDGET_EXCEEDED"
        result["speech"] = (
            f"One verified option lot requires about {estimated_premium:.2f} premium, above the current "
            f"paper premium budget of {max_premium:.2f}. No paper position was opened."
        )
        return result

    intent["lot_size"] = resolved_lot
    intent["quantity_units"] = resolved_lot * int(intent.get("quantity_lots") or 1)
    intent["estimated_premium"] = estimated_premium
    intent["paper_equity"] = paper_equity
    intent["max_premium_budget"] = max_premium
    intent["contract_validated"] = True
    result["paper_intent"] = intent
    result["risk_gate"] = "PAPER_OPTION_INTENT_VALIDATED"
    result["paper_only"] = True
    result["live_execution"] = False
    return result
