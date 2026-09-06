from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DERIBIT_HTTP = "https://www.deribit.com/api/v2"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAPER_OPTION_JOURNAL = PROJECT_ROOT / "data" / "trading" / "paper_options.jsonl"

SUPPORTED = {"BTC": "BTC", "BITCOIN": "BTC", "ETH": "ETH", "ETHEREUM": "ETH"}


@dataclass(frozen=True)
class OptionRequest:
    underlying: str
    strike: float | None
    option_type: str | None
    expiry_date: str | None
    buy_requested: bool
    paper_requested: bool
    raw: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _json(url: str, params: dict[str, Any], timeout: float = 8.0) -> Any:
    request = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "JARVIS-Quant-Options/3.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(str(payload["error"])[:500])
    return payload.get("result") if isinstance(payload, dict) else payload


def parse_option_request(text: str, today: date | None = None) -> OptionRequest | None:
    raw = str(text or "").strip()
    value = raw.lower()
    if "option" not in value and " call" not in value and " put" not in value:
        return None

    underlying = None
    for alias, canonical in SUPPORTED.items():
        if re.search(rf"\b{re.escape(alias.lower())}\b", value):
            underlying = canonical
            break
    if underlying is None:
        return None

    option_type = None
    if re.search(r"\b(call|ce)\b", value):
        option_type = "call"
    elif re.search(r"\b(put|pe)\b", value):
        option_type = "put"

    strike = None
    numbers = [float(item.replace(",", "")) for item in re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", value)]
    plausible = [number for number in numbers if number >= 100]
    if plausible:
        strike = plausible[0]

    base = today or datetime.now(timezone.utc).date()
    expiry = None
    if "tomorrow" in value:
        expiry = base + timedelta(days=1)
    elif "today" in value:
        expiry = base
    else:
        iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", value)
        if iso:
            expiry = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        else:
            slash = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", value)
            if slash:
                year = int(slash.group(3) or base.year)
                expiry = date(year, int(slash.group(2)), int(slash.group(1)))

    return OptionRequest(
        underlying=underlying,
        strike=strike,
        option_type=option_type,
        expiry_date=expiry.isoformat() if expiry else None,
        buy_requested=bool(re.search(r"\b(buy|purchase|take|enter)\b", value)),
        paper_requested="paper" in value,
        raw=raw,
    )


def _instruments(currency: str) -> list[dict[str, Any]]:
    result = _json(
        DERIBIT_HTTP + "/public/get_instruments",
        {"currency": currency, "kind": "option", "expired": "false"},
    )
    return list(result or [])


def _book_summaries(currency: str) -> list[dict[str, Any]]:
    """Return Deribit's public bulk option snapshot for one currency."""

    result = _json(
        DERIBIT_HTTP + "/public/get_book_summary_by_currency",
        {"currency": currency, "kind": "option"},
    )
    return [dict(row) for row in result or [] if isinstance(row, dict)]


def _ticker(instrument_name: str) -> dict[str, Any]:
    result = _json(
        DERIBIT_HTTP + "/public/ticker",
        {"instrument_name": instrument_name},
    )
    return dict(result or {})


def _expiry_date(instrument: dict[str, Any]) -> date:
    return datetime.fromtimestamp(
        float(instrument["expiration_timestamp"]) / 1000.0,
        tz=timezone.utc,
    ).date()


def _matches(request: OptionRequest, instruments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = instruments
    if request.expiry_date:
        target = date.fromisoformat(request.expiry_date)
        rows = [item for item in rows if _expiry_date(item) == target]
    if request.strike is not None:
        rows = [item for item in rows if math.isclose(float(item.get("strike") or 0.0), request.strike, rel_tol=0.0, abs_tol=1e-9)]
    if request.option_type:
        rows = [item for item in rows if str(item.get("option_type") or "").lower() == request.option_type]
    return rows


def _available_expiries(instruments: list[dict[str, Any]]) -> list[str]:
    return sorted({_expiry_date(item).isoformat() for item in instruments})


def option_chain_snapshot(
    currency: str,
    *,
    expiry: str | None = None,
    max_strikes: int = 25,
) -> dict[str, Any]:
    """Load a bounded, verified Deribit option chain without credentials.

    Bulk summaries expose quotes, OI, volume and mark IV, but not contract
    Greeks.  Those values deliberately stay ``None``; the existing exact
    contract ticker path remains the source for delta/gamma/theta/vega.
    """

    canonical = SUPPORTED.get(str(currency or "").strip().upper())
    if canonical is None:
        raise ValueError(f"Unsupported Deribit option currency: {currency}")

    instruments = _instruments(canonical)
    expiries = _available_expiries(instruments)
    if not expiries:
        return {
            "success": False,
            "provider": "DERIBIT_PUBLIC",
            "symbol": canonical,
            "available_expiries": [],
            "chain": [],
            "message": "Deribit returned no active listed option expiries.",
            "paper_only": True,
            "live_execution": False,
        }

    selected_expiry = str(expiry or expiries[0])
    if selected_expiry not in expiries:
        return {
            "success": False,
            "provider": "DERIBIT_PUBLIC",
            "symbol": canonical,
            "expiry": selected_expiry,
            "available_expiries": expiries,
            "chain": [],
            "message": f"Deribit does not list {canonical} options for {selected_expiry}.",
            "paper_only": True,
            "live_execution": False,
        }

    selected = [
        row for row in instruments
        if _expiry_date(row).isoformat() == selected_expiry
    ]
    summaries = {
        str(row.get("instrument_name") or ""): row
        for row in _book_summaries(canonical)
    }
    spot = next(
        (
            float(value)
            for row in summaries.values()
            for value in (row.get("underlying_price"),)
            if value is not None and float(value) > 0
        ),
        None,
    )

    strikes = sorted({float(row.get("strike") or 0.0) for row in selected if float(row.get("strike") or 0.0) > 0})
    bounded_strikes = max(1, min(int(max_strikes), 60))
    if spot is not None and len(strikes) > bounded_strikes:
        strikes = sorted(strikes, key=lambda value: abs(value - spot))[:bounded_strikes]
        strikes.sort()
    allowed_strikes = set(strikes)

    raw_rows: list[dict[str, Any]] = []
    for instrument in selected:
        strike = float(instrument.get("strike") or 0.0)
        if strike not in allowed_strikes:
            continue
        name = str(instrument.get("instrument_name") or "")
        summary = summaries.get(name, {})
        kind = str(instrument.get("option_type") or "").lower()
        raw_rows.append(
            {
                "instrument_name": name,
                "expiry": selected_expiry,
                "strike": strike,
                "option_type": "CE" if kind == "call" else "PE" if kind == "put" else kind,
                "ltp": summary.get("last"),
                "bid": summary.get("bid_price"),
                "ask": summary.get("ask_price"),
                "open_interest": summary.get("open_interest"),
                "volume": summary.get("volume"),
                "iv": summary.get("mark_iv"),
                "delta": None,
                "gamma": None,
                "theta": None,
                "vega": None,
                "mark_price": summary.get("mark_price"),
                "quote_currency": summary.get("quote_currency"),
            }
        )

    from workstation.options_chain_analytics import analyze_chain, normalize_contracts

    normalized = normalize_contracts(
        raw_rows,
        underlying=canonical,
        provider="DERIBIT_PUBLIC",
        expiry=selected_expiry,
        provider_symbol=canonical,
    )
    analytics = analyze_chain(normalized, spot=spot, verified=True, stale=False)
    # Deribit inverse option premiums are quoted in the base coin.  Adding a
    # coin-denominated straddle to a USD spot would be dimensionally wrong.
    analytics["expected_move"] = None
    analytics["expected_move_reason"] = "OPTION_PREMIUM_AND_SPOT_CURRENCIES_DIFFER"
    return {
        "success": bool(normalized),
        "provider": "DERIBIT_PUBLIC",
        "source": "DERIBIT_PUBLIC_BULK_OPTION_SUMMARY",
        "symbol": canonical,
        "provider_symbol": canonical,
        "expiry": selected_expiry,
        "available_expiries": expiries,
        "spot": spot,
        "chain": [item.to_dict() for item in normalized],
        "chain_analytics": analytics,
        "total_contracts_available": len(selected),
        "displayed_contracts": len(normalized),
        "greeks_status": "EXACT_CONTRACT_TICKER_REQUIRED",
        "message": (
            f"Verified Deribit bulk chain loaded for {canonical} {selected_expiry}. "
            "Quotes, OI, volume and mark IV are live public fields; Greeks require an exact contract ticker."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "live_execution": False,
    }


def _paper_quantity(ticker: dict[str, Any], instrument: dict[str, Any], equity: float = 100000.0, risk_fraction: float = 0.005) -> float:
    mark = float(ticker.get("mark_price") or 0.0)
    underlying = float(ticker.get("underlying_price") or ticker.get("index_price") or 0.0)
    contract_size = float(instrument.get("contract_size") or 1.0)
    minimum = float(instrument.get("min_trade_amount") or 0.1)
    premium_usd = mark * underlying * contract_size
    if premium_usd <= 0:
        return 0.0
    raw = (equity * risk_fraction) / premium_usd
    if raw < minimum:
        return 0.0
    steps = math.floor(raw / minimum)
    return round(steps * minimum, 8)


def _journal(intent: dict[str, Any]) -> None:
    PAPER_OPTION_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with PAPER_OPTION_JOURNAL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(intent, sort_keys=True) + "\n")


def option_command_payload(text: str, *, today: date | None = None, paper_execute: bool = True) -> dict[str, Any] | None:
    request = parse_option_request(text, today=today)
    if request is None:
        return None

    instruments = _instruments(request.underlying)
    expiries = _available_expiries(instruments)
    matches = _matches(request, instruments)

    response: dict[str, Any] = {
        "action": "option_analysis",
        "request": request.to_dict(),
        "provider": "DERIBIT_PUBLIC",
        "available_expiries": expiries[:20],
        "candidates": [],
        "paper_intent": None,
        "paper_only": True,
        "live_execution": False,
    }

    if request.expiry_date and not any(_expiry_date(item).isoformat() == request.expiry_date for item in instruments):
        nearest = min(expiries, key=lambda item: abs((date.fromisoformat(item) - date.fromisoformat(request.expiry_date)).days)) if expiries else None
        response["speech"] = (
            f"No {request.underlying} option expiry is listed for {request.expiry_date}. "
            + (f"Nearest listed expiry is {nearest}. " if nearest else "")
            + "No paper trade was created."
        )
        return response

    if request.strike is None:
        response["speech"] = "Specify the option strike so I can inspect the exact contract. No paper trade was created."
        return response

    if not matches and request.option_type is None:
        matches = [item for item in instruments if math.isclose(float(item.get("strike") or 0.0), request.strike, rel_tol=0.0, abs_tol=1e-9)]
        if request.expiry_date:
            matches = [item for item in matches if _expiry_date(item).isoformat() == request.expiry_date]

    candidates = []
    for item in matches[:6]:
        ticker = _ticker(str(item["instrument_name"]))
        candidates.append(
            {
                "instrument_name": item["instrument_name"],
                "expiry": _expiry_date(item).isoformat(),
                "strike": float(item.get("strike") or 0.0),
                "option_type": item.get("option_type"),
                "best_bid": ticker.get("best_bid_price"),
                "best_ask": ticker.get("best_ask_price"),
                "mark_price": ticker.get("mark_price"),
                "mark_iv": ticker.get("mark_iv"),
                "open_interest": ticker.get("open_interest"),
                "underlying_price": ticker.get("underlying_price") or ticker.get("index_price"),
                "greeks": ticker.get("greeks") or {},
                "state": ticker.get("state"),
            }
        )
    response["candidates"] = candidates

    if not candidates:
        response["speech"] = "No exact listed option contract matched the requested strike and expiry. No paper trade was created."
        return response

    if request.option_type is None:
        names = ", ".join(f"{row['option_type'].upper()} {row['instrument_name']}" for row in candidates[:4])
        response["speech"] = (
            f"I found the {request.underlying} {request.strike:g} option request, but call versus put is ambiguous. "
            f"Available matches: {names}. Say call or put. No paper trade was created."
        )
        return response

    selected = candidates[0]
    instrument = next(item for item in matches if item["instrument_name"] == selected["instrument_name"])
    ticker = _ticker(selected["instrument_name"])
    quantity = _paper_quantity(ticker, instrument)

    if request.buy_requested and paper_execute:
        if quantity <= 0:
            response["speech"] = "The option exists, but the synthetic risk budget is too small for the minimum contract size at the current premium. No paper trade was created."
            return response
        intent = {
            "instrument_name": selected["instrument_name"],
            "underlying": request.underlying,
            "side": "BUY",
            "option_type": request.option_type,
            "strike": request.strike,
            "expiry": selected["expiry"],
            "quantity": quantity,
            "reference_mark_price": selected["mark_price"],
            "reference_underlying_price": selected["underlying_price"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "PAPER_OPTION_INTENT",
            "provider": "DERIBIT_PUBLIC",
            "live_execution": False,
        }
        _journal(intent)
        response["paper_intent"] = intent
        response["speech"] = (
            f"Paper option intent created for {selected['instrument_name']}, quantity {quantity:g}, "
            f"using the current public mark as the reference. Live execution remains locked."
        )
        return response

    response["speech"] = (
        f"Option contract found: {selected['instrument_name']}. Mark IV {selected.get('mark_iv')}. "
        "This is analysis only; no paper trade was created."
    )
    return response
