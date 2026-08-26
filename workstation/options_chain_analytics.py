"""Provider-neutral, descriptive options-chain analytics.

The module never fetches data and never creates an order.  Missing provider
fields remain ``None`` instead of being estimated.  Max pain and OI walls are
descriptive concentration measures, not forecasts or execution signals.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from typing import Any, Iterable


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _option_type(value: Any) -> str | None:
    item = str(value or "").upper()
    if item in {"CE", "CALL", "C"}:
        return "CE"
    if item in {"PE", "PUT", "P"}:
        return "PE"
    return None


@dataclass(frozen=True)
class NormalizedOptionContract:
    symbol: str | None
    underlying: str
    expiry: str | None
    strike: float
    option_type: str
    ltp: float | None
    bid: float | None
    ask: float | None
    open_interest: float | None
    change_in_oi: float | None
    volume: float | None
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    provider: str
    provider_symbol: str | None

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.ask is None or self.ask < self.bid:
            return None
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float | None:
        if self.bid is None or self.ask is None or self.ask < self.bid:
            return None
        return self.ask - self.bid

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["mid"] = self.mid
        value["spread"] = self.spread
        return value


def normalize_contracts(
    rows: Iterable[dict[str, Any]],
    *,
    underlying: str,
    provider: str,
    expiry: str | None = None,
    provider_symbol: str | None = None,
) -> tuple[NormalizedOptionContract, ...]:
    contracts = []
    for row in rows:
        kind = _option_type(row.get("option_type") or row.get("type"))
        strike = _number(row.get("strike") if row.get("strike") is not None else row.get("strike_price"))
        if kind is None or strike is None or strike <= 0:
            continue
        greeks = row.get("greeks") if isinstance(row.get("greeks"), dict) else {}
        contracts.append(
            NormalizedOptionContract(
                symbol=str(row.get("symbol") or row.get("instrument_name") or "") or None,
                underlying=str(underlying).upper(),
                expiry=str(row.get("expiry") or expiry or "") or None,
                strike=strike,
                option_type=kind,
                ltp=_number(row.get("ltp") if row.get("ltp") is not None else row.get("last_price")),
                bid=_number(row.get("bid") if row.get("bid") is not None else row.get("best_bid")),
                ask=_number(row.get("ask") if row.get("ask") is not None else row.get("best_ask")),
                open_interest=_number(row.get("open_interest") if row.get("open_interest") is not None else row.get("oi")),
                change_in_oi=_number(row.get("change_in_oi") if row.get("change_in_oi") is not None else row.get("oich")),
                volume=_number(row.get("volume")),
                iv=_number(row.get("iv") if row.get("iv") is not None else greeks.get("iv")),
                delta=_number(row.get("delta") if row.get("delta") is not None else greeks.get("delta")),
                gamma=_number(row.get("gamma") if row.get("gamma") is not None else greeks.get("gamma")),
                theta=_number(row.get("theta") if row.get("theta") is not None else greeks.get("theta")),
                vega=_number(row.get("vega") if row.get("vega") is not None else greeks.get("vega")),
                provider=str(provider),
                provider_symbol=provider_symbol,
            )
        )
    return tuple(contracts)


def _premium(contract: NormalizedOptionContract) -> float | None:
    return contract.mid if contract.mid is not None else contract.ltp


def _max_pain(contracts: tuple[NormalizedOptionContract, ...]) -> dict[str, Any] | None:
    eligible = [item for item in contracts if item.open_interest is not None and item.open_interest > 0]
    strikes = sorted({item.strike for item in eligible})
    if not strikes:
        return None
    payouts = {}
    for settlement in strikes:
        payout = 0.0
        for item in eligible:
            intrinsic = (
                max(settlement - item.strike, 0.0)
                if item.option_type == "CE"
                else max(item.strike - settlement, 0.0)
            )
            payout += intrinsic * float(item.open_interest or 0.0)
        payouts[settlement] = payout
    strike = min(payouts, key=payouts.get)
    return {
        "strike": strike,
        "aggregate_intrinsic_payout": payouts[strike],
        "descriptive_only": True,
    }


def analyze_chain(
    contracts: Iterable[NormalizedOptionContract],
    *,
    spot: float | None,
    received_at: str | None = None,
    verified: bool = True,
    stale: bool = False,
) -> dict[str, Any]:
    rows = tuple(contracts)
    spot_value = _number(spot)
    call_oi = sum(item.open_interest or 0.0 for item in rows if item.option_type == "CE")
    put_oi = sum(item.open_interest or 0.0 for item in rows if item.option_type == "PE")
    call_wall = max((item for item in rows if item.option_type == "CE" and item.open_interest is not None), key=lambda item: item.open_interest or 0.0, default=None)
    put_wall = max((item for item in rows if item.option_type == "PE" and item.open_interest is not None), key=lambda item: item.open_interest or 0.0, default=None)

    expected_move = None
    if spot_value is not None and spot_value > 0:
        calls = [item for item in rows if item.option_type == "CE" and _premium(item) is not None]
        puts = [item for item in rows if item.option_type == "PE" and _premium(item) is not None]
        if calls and puts:
            call = min(calls, key=lambda item: abs(item.strike - spot_value))
            same_puts = [item for item in puts if item.strike == call.strike and item.expiry == call.expiry]
            if same_puts:
                put = same_puts[0]
                amount = float(_premium(call)) + float(_premium(put))
                expected_move = {"strike": call.strike, "amount": amount, "percent_of_spot": amount / spot_value * 100.0}

    delta_calls = [item for item in rows if item.option_type == "CE" and item.delta is not None and item.iv is not None]
    delta_puts = [item for item in rows if item.option_type == "PE" and item.delta is not None and item.iv is not None]
    skew = None
    if delta_calls and delta_puts:
        call = min(delta_calls, key=lambda item: abs(float(item.delta) - 0.25))
        put = min(delta_puts, key=lambda item: abs(abs(float(item.delta)) - 0.25))
        skew = {"put_25d_iv": put.iv, "call_25d_iv": call.iv, "put_minus_call_iv": float(put.iv) - float(call.iv)}

    gamma_by_strike: dict[float, float] = defaultdict(float)
    for item in rows:
        if item.gamma is not None and item.open_interest is not None:
            gamma_by_strike[item.strike] += abs(item.gamma) * max(item.open_interest, 0.0)
    gamma_concentration = [
        {"strike": strike, "absolute_gamma_oi": value}
        for strike, value in sorted(gamma_by_strike.items(), key=lambda pair: pair[1], reverse=True)[:5]
    ]

    quoted = [item for item in rows if item.mid is not None and item.spread is not None and item.mid and item.mid > 0]
    liquid = [item for item in quoted if float(item.spread) / float(item.mid) <= 0.15]
    liquidity = {
        "quoted_contracts": len(quoted),
        "contracts_with_relative_spread_at_most_15pct": len(liquid),
        "coverage": (len(liquid) / len(rows)) if rows else 0.0,
        "threshold_is_policy_not_market_fact": True,
    }

    expiries: dict[str, list[NormalizedOptionContract]] = defaultdict(list)
    for item in rows:
        if item.expiry and item.iv is not None:
            expiries[item.expiry].append(item)
    term_structure = []
    if spot_value is not None:
        for expiry, items in sorted(expiries.items()):
            atm = min(items, key=lambda item: abs(item.strike - spot_value))
            term_structure.append({"expiry": expiry, "atm_reference_strike": atm.strike, "atm_reference_iv": atm.iv})

    return {
        "success": bool(rows),
        "contract_count": len(rows),
        "spot": spot_value,
        "pcr_oi": (put_oi / call_oi) if call_oi > 0 else None,
        "call_oi": call_oi if rows else None,
        "put_oi": put_oi if rows else None,
        "call_oi_wall": ({"strike": call_wall.strike, "open_interest": call_wall.open_interest} if call_wall else None),
        "put_oi_wall": ({"strike": put_wall.strike, "open_interest": put_wall.open_interest} if put_wall else None),
        "max_pain": _max_pain(rows),
        "expected_move": expected_move,
        "skew_25_delta": skew,
        "term_structure": term_structure,
        "gamma_concentration": gamma_concentration,
        "liquidity": liquidity,
        "received_at": received_at or datetime.now(timezone.utc).isoformat(),
        "verified": bool(verified),
        "stale": bool(stale),
        "descriptive_not_predictive": True,
        "paper_only": True,
        "live_execution": False,
    }

