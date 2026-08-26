"""Verified instrument accounting for the synthetic Paper Desk.

The Paper Desk records contracts/units, never broker orders.  This module keeps
provider contract metadata separate from strategy decisions and fails closed
for derivatives when lot/tick information has not been verified.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


DERIVATIVE_TYPES = {"FUTURE", "OPTION", "COMMODITY", "DERIVATIVE"}


def _positive(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class PaperInstrumentSpec:
    symbol: str
    provider_symbol: str
    asset_class: str
    instrument_type: str
    native_currency: str
    valuation_currency: str
    quantity_step: float
    contract_multiplier: float
    tick_size: float | None
    source: str
    verified: bool
    verification_reason: str
    cost_model_status: str = "UNCONFIGURED"

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "PaperInstrumentSpec | None":
        if not isinstance(value, dict):
            return None
        tick = _positive(value.get("tick_size"))
        return cls(
            symbol=str(value.get("symbol") or "").strip().upper(),
            provider_symbol=str(value.get("provider_symbol") or value.get("symbol") or "").strip(),
            asset_class=str(value.get("asset_class") or "UNKNOWN").strip().upper(),
            instrument_type=str(value.get("instrument_type") or value.get("asset_class") or "SPOT").strip().upper(),
            native_currency=str(value.get("native_currency") or value.get("currency") or "").strip().upper(),
            valuation_currency=str(value.get("valuation_currency") or "INR").strip().upper(),
            quantity_step=_positive(value.get("quantity_step"), 1.0),
            contract_multiplier=_positive(value.get("contract_multiplier"), 1.0),
            tick_size=tick or None,
            source=str(value.get("source") or "UNVERIFIED").strip().upper(),
            verified=bool(value.get("verified")),
            verification_reason=str(value.get("verification_reason") or "UNSPECIFIED"),
            cost_model_status=str(value.get("cost_model_status") or "UNCONFIGURED").strip().upper(),
        )

    @property
    def derivative(self) -> bool:
        return self.instrument_type in DERIVATIVE_TYPES or self.asset_class in DERIVATIVE_TYPES

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_instrument_spec(
    value: dict[str, Any] | None,
    *,
    asset_type: str,
) -> tuple[PaperInstrumentSpec | None, str | None]:
    spec = PaperInstrumentSpec.from_mapping(value)
    derivative_requested = str(asset_type or "").strip().upper() in DERIVATIVE_TYPES
    if spec is None:
        return (None, "DERIVATIVE_SPEC_REQUIRED" if derivative_requested else None)
    if not spec.verified:
        return (spec, "INSTRUMENT_SPEC_UNVERIFIED" if (derivative_requested or spec.derivative) else None)
    if (derivative_requested or spec.derivative) and (
        spec.contract_multiplier <= 0 or spec.quantity_step <= 0 or not spec.tick_size
    ):
        return spec, "DERIVATIVE_SPEC_INCOMPLETE"
    return spec, None


def quantize_quantity(quantity: float, step: float) -> float:
    step_value = _positive(step, 1.0)
    bounded = max(float(quantity), 0.0)
    # Small epsilon prevents a value already on the grid from losing a step.
    return math.floor((bounded + step_value * 1e-10) / step_value) * step_value


def quantize_price(price: float | None, tick: float | None, *, mode: str = "nearest") -> float | None:
    if price is None:
        return None
    value = float(price)
    tick_value = _positive(tick)
    if tick_value <= 0:
        return value
    units = value / tick_value
    if mode == "floor":
        rounded = math.floor(units + 1e-10)
    elif mode == "ceil":
        rounded = math.ceil(units - 1e-10)
    else:
        rounded = round(units)
    return rounded * tick_value


def normalized_price_grid(
    *,
    side: str,
    entry: float,
    stop: float | None,
    target: float | None,
    tick_size: float | None,
) -> tuple[float, float | None, float | None]:
    resolved_side = str(side).upper()
    normalized_entry = float(quantize_price(entry, tick_size) or entry)
    if resolved_side == "LONG":
        normalized_stop = quantize_price(stop, tick_size, mode="floor")
        normalized_target = quantize_price(target, tick_size, mode="floor")
    else:
        normalized_stop = quantize_price(stop, tick_size, mode="ceil")
        normalized_target = quantize_price(target, tick_size, mode="ceil")
    return normalized_entry, normalized_stop, normalized_target
